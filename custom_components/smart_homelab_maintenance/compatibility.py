"""Conservative integration/agent compatibility evaluation."""

from __future__ import annotations

from dataclasses import dataclass

from .const import AGENT_API_CONTRACT, VERSION


@dataclass(frozen=True, slots=True)
class Compatibility:
    status: str
    expected_version: str
    observed_version: str | None
    expected_contract: str
    observed_contract: str | None
    reason: str

    def as_attributes(self) -> dict[str, str | None]:
        return {
            "compatibility_status": self.status,
            "expected_agent_version": self.expected_version,
            "agent_version": self.observed_version,
            "expected_api_contract": self.expected_contract,
            "agent_api_contract": self.observed_contract,
            "compatibility_reason": self.reason,
        }


def evaluate_agent(agent_version: object, api_contract: object) -> Compatibility:
    """Classify without guessing when health data is incomplete."""

    observed_version = agent_version if isinstance(agent_version, str) and agent_version else None
    observed_contract = api_contract if isinstance(api_contract, str) and api_contract else None
    if observed_version is None or observed_contract is None:
        return Compatibility("unknown", VERSION, observed_version, AGENT_API_CONTRACT, observed_contract, "health data incomplete")
    if observed_contract != AGENT_API_CONTRACT:
        return Compatibility("incompatible", VERSION, observed_version, AGENT_API_CONTRACT, observed_contract, "API contract mismatch")
    if observed_version == VERSION:
        return Compatibility("current", VERSION, observed_version, AGENT_API_CONTRACT, observed_contract, "versions and contract match")
    if observed_version.startswith("0.") and VERSION.startswith("0."):
        return Compatibility("outdated", VERSION, observed_version, AGENT_API_CONTRACT, observed_contract, "agent version is older than integration")
    return Compatibility("incompatible", VERSION, observed_version, AGENT_API_CONTRACT, observed_contract, "unsupported agent version")
