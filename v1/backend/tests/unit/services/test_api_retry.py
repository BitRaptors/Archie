"""Tests for API retry logic in PhasedBlueprintGenerator."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from anthropic import APIConnectionError, APITimeoutError, InternalServerError, RateLimitError, AuthenticationError, BadRequestError


def _make_response(status_code: int = 200) -> httpx.Response:
    """Build a minimal httpx.Response for anthropic exception constructors."""
    return httpx.Response(status_code=status_code, request=httpx.Request("POST", "https://api.anthropic.com"))


def _make_success_response():
    """Build a mock successful API response."""
    return MagicMock(content=[MagicMock(text='{"result": "ok"}')])


def _make_internal_server_error():
    """Build an InternalServerError (529 overloaded)."""
    return InternalServerError(
        message="Overloaded",
        response=_make_response(529),
        body={"error": {"message": "Overloaded", "type": "overloaded_error"}},
    )


def _make_rate_limit_error():
    """Build a RateLimitError (429)."""
    return RateLimitError(
        message="Rate limited",
        response=_make_response(429),
        body={"error": {"message": "Rate limited", "type": "rate_limit_error"}},
    )


@pytest.fixture
def generator_and_client(mock_settings):
    """Create a PhasedBlueprintGenerator with a mock client for _call_ai tests."""
    with patch("anthropic.AsyncAnthropic") as mock_anthropic:
        mock_client = AsyncMock()
        mock_anthropic.return_value = mock_client

        from application.services.phased_blueprint_generator import PhasedBlueprintGenerator

        gen = PhasedBlueprintGenerator(settings=mock_settings)
        gen._client = mock_client
        return gen, mock_client


class TestCallAiRetryLogic:
    """Tests for the _call_ai() application-level retry wrapper."""

    @pytest.mark.asyncio
    async def test_success_on_first_attempt(self, generator_and_client):
        """No retries needed when the first call succeeds."""
        gen, mock_client = generator_and_client
        mock_client.messages.create = AsyncMock(return_value=_make_success_response())

        result = await gen._call_ai(
            phase_name="discovery",
            analysis_id="a1",
            model="claude-3-haiku-20240307",
            max_tokens=100,
            messages=[{"role": "user", "content": "hi"}],
        )

        assert result.content[0].text == '{"result": "ok"}'
        assert mock_client.messages.create.call_count == 1

    @pytest.mark.asyncio
    async def test_retries_on_internal_server_error(self, generator_and_client):
        """Two failures then success — should make 3 calls and sleep twice."""
        gen, mock_client = generator_and_client
        mock_client.messages.create = AsyncMock(
            side_effect=[
                _make_internal_server_error(),
                _make_internal_server_error(),
                _make_success_response(),
            ]
        )

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await gen._call_ai(
                phase_name="communication",
                analysis_id="a2",
                model="m",
                max_tokens=100,
                messages=[],
            )

        assert result.content[0].text == '{"result": "ok"}'
        assert mock_client.messages.create.call_count == 3
        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(30)
        mock_sleep.assert_any_call(60)

    @pytest.mark.asyncio
    async def test_retries_on_rate_limit_error(self, generator_and_client):
        """One 429 failure then success."""
        gen, mock_client = generator_and_client
        mock_client.messages.create = AsyncMock(
            side_effect=[
                _make_rate_limit_error(),
                _make_success_response(),
            ]
        )

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await gen._call_ai(
                phase_name="layers",
                analysis_id="a3",
                model="m",
                max_tokens=100,
                messages=[],
            )

        assert result.content[0].text == '{"result": "ok"}'
        assert mock_client.messages.create.call_count == 2
        mock_sleep.assert_called_once_with(30)

    @pytest.mark.asyncio
    async def test_no_retry_on_authentication_error(self, generator_and_client):
        """AuthenticationError (401) should propagate immediately."""
        gen, mock_client = generator_and_client
        mock_client.messages.create = AsyncMock(
            side_effect=AuthenticationError(
                message="Invalid key",
                response=_make_response(401),
                body={"error": {"message": "Invalid key", "type": "authentication_error"}},
            )
        )

        with pytest.raises(AuthenticationError):
            await gen._call_ai(
                phase_name="discovery",
                model="m",
                max_tokens=100,
                messages=[],
            )

        assert mock_client.messages.create.call_count == 1

    @pytest.mark.asyncio
    async def test_no_retry_on_bad_request_error(self, generator_and_client):
        """BadRequestError (400) should propagate immediately."""
        gen, mock_client = generator_and_client
        mock_client.messages.create = AsyncMock(
            side_effect=BadRequestError(
                message="Bad request",
                response=_make_response(400),
                body={"error": {"message": "Bad request", "type": "invalid_request_error"}},
            )
        )

        with pytest.raises(BadRequestError):
            await gen._call_ai(
                phase_name="patterns",
                model="m",
                max_tokens=100,
                messages=[],
            )

        assert mock_client.messages.create.call_count == 1

    @pytest.mark.asyncio
    async def test_max_retries_exhausted_raises_original(self, generator_and_client):
        """All 4 attempts fail — should raise InternalServerError after 3 sleeps."""
        gen, mock_client = generator_and_client
        mock_client.messages.create = AsyncMock(
            side_effect=[
                _make_internal_server_error(),
                _make_internal_server_error(),
                _make_internal_server_error(),
                _make_internal_server_error(),
            ]
        )

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(InternalServerError):
                await gen._call_ai(
                    phase_name="synthesis",
                    analysis_id="a4",
                    model="m",
                    max_tokens=100,
                    messages=[],
                )

        assert mock_client.messages.create.call_count == 4
        assert mock_sleep.call_count == 3
        mock_sleep.assert_any_call(30)
        mock_sleep.assert_any_call(60)
        mock_sleep.assert_any_call(120)

    @pytest.mark.asyncio
    async def test_progress_callback_called_during_retries(self, generator_and_client):
        """Verify progress callback is invoked with WARNING on retries."""
        gen, mock_client = generator_and_client
        mock_client.messages.create = AsyncMock(
            side_effect=[
                _make_internal_server_error(),
                _make_success_response(),
            ]
        )
        gen._progress_callback = AsyncMock()

        with patch("asyncio.sleep", new_callable=AsyncMock):
            await gen._call_ai(
                phase_name="technology",
                analysis_id="a5",
                model="m",
                max_tokens=100,
                messages=[],
            )

        gen._progress_callback.assert_called_once()
        call_args = gen._progress_callback.call_args[0]
        assert call_args[0] == "a5"  # analysis_id
        assert call_args[1] == "WARNING"  # event_type
        assert "technology" in call_args[2]  # phase name in message

    @pytest.mark.asyncio
    async def test_succeeds_on_third_attempt(self, generator_and_client):
        """Two failures then success on the 3rd attempt."""
        gen, mock_client = generator_and_client
        mock_client.messages.create = AsyncMock(
            side_effect=[
                _make_rate_limit_error(),
                _make_internal_server_error(),
                _make_success_response(),
            ]
        )

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await gen._call_ai(
                phase_name="observation",
                analysis_id="a6",
                model="m",
                max_tokens=100,
                messages=[],
            )

        assert result.content[0].text == '{"result": "ok"}'
        assert mock_client.messages.create.call_count == 3
        assert mock_sleep.call_count == 2


    @pytest.mark.asyncio
    async def test_retries_on_connection_error(self, generator_and_client):
        """APIConnectionError (network issues, read errors) should be retried."""
        gen, mock_client = generator_and_client
        mock_client.messages.create = AsyncMock(
            side_effect=[
                APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com")),
                _make_success_response(),
            ]
        )

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await gen._call_ai(
                phase_name="layers",
                analysis_id="a7",
                model="m",
                max_tokens=100,
                messages=[],
            )

        assert result.content[0].text == '{"result": "ok"}'
        assert mock_client.messages.create.call_count == 2
        mock_sleep.assert_called_once_with(30)

    @pytest.mark.asyncio
    async def test_retries_on_timeout_error(self, generator_and_client):
        """APITimeoutError (request timeout) should be retried."""
        gen, mock_client = generator_and_client
        mock_client.messages.create = AsyncMock(
            side_effect=[
                APITimeoutError(request=httpx.Request("POST", "https://api.anthropic.com")),
                _make_success_response(),
            ]
        )

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await gen._call_ai(
                phase_name="patterns",
                analysis_id="a8",
                model="m",
                max_tokens=100,
                messages=[],
            )

        assert result.content[0].text == '{"result": "ok"}'
        assert mock_client.messages.create.call_count == 2
        mock_sleep.assert_called_once_with(30)


class TestSdkLevelRetryConfig:
    """Tests verifying the SDK-level retry configuration."""

    def test_client_has_max_retries_set(self, mock_settings):
        """Verify AsyncAnthropic is constructed with max_retries=5."""
        with patch("application.services.phased_blueprint_generator.AsyncAnthropic") as mock_anthropic:
            from application.services.phased_blueprint_generator import PhasedBlueprintGenerator

            PhasedBlueprintGenerator(settings=mock_settings)

            mock_anthropic.assert_called_once()
            call_kwargs = mock_anthropic.call_args[1]
            assert call_kwargs["max_retries"] == 5
