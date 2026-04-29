export function RuleCard() {
  return (
    <div className="border-2 border-princeton-orange bg-black shadow-[8px_8px_0px_0px_#fb8500] font-mono text-[13px] leading-relaxed overflow-hidden">
      {/* Header bar */}
      <div className="bg-princeton-orange/10 border-b border-princeton-orange/30 px-4 py-2 flex items-center justify-between">
        <span className="text-princeton-orange uppercase tracking-widest text-[10px]">
          {">"} .archie/rules.json
        </span>
        <span className="text-gray-500 text-[10px] uppercase tracking-widest">rule</span>
      </div>

      <div className="p-5 text-gray-300 space-y-4">
        <div>
          <div className="text-sky-blue font-bold mb-1">name:</div>
          <div className="text-neon">domain_layer_boundary</div>
        </div>

        <div>
          <div className="text-sky-blue font-bold mb-1">severity_class:</div>
          <div className="text-princeton-orange">decision_violation</div>
        </div>

        <div>
          <div className="text-sky-blue font-bold mb-1">DESCRIPTION</div>
          <div>
            Domain layer must not import from
            <br />
            infrastructure or API layers.
          </div>
        </div>

        <div>
          <div className="text-sky-blue font-bold mb-1">WHY</div>
          <div className="text-gray-400">
            Forced by: clean architecture decision.
            <br />
            Enables: independent testability of
            <br />
            business logic, swappable adapters.
          </div>
        </div>

        <div>
          <div className="text-sky-blue font-bold mb-1">EXAMPLE</div>
          <div>
            <span className="text-neon">✓</span>{" "}
            <span className="text-gray-300">from domain.entities import User</span>
          </div>
          <div>
            <span className="text-princeton-orange">✗</span>{" "}
            <span className="text-gray-300">from infrastructure.db import Session</span>
          </div>
        </div>
      </div>
    </div>
  )
}
