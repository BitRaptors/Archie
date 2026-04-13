create table reports (
  id uuid primary key default gen_random_uuid(),
  token text unique not null,
  bundle jsonb not null,
  size_bytes integer not null,
  created_at timestamptz default now()
);

create index idx_reports_token on reports (token);

alter table reports enable row level security;
