"""Conservative integration/agent compatibility evaluation."""

from __future__ import annotations

from dataclasses import dataclass
import re

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
    expected_beta = re.fullmatch(r"(0\.\d+\.\d+)-beta\.(\d+)", VERSION)
    observed_beta = re.fullmatch(r"(0\.\d+\.\d+)-beta\.(\d+)", observed_version)
    if expected_beta and observed_beta and expected_beta.group(1) == observed_beta.group(1):
        return Compatibility("current", VERSION, observed_version, AGENT_API_CONTRACT, observed_contract, "beta release line and API contract match")
    expected_rc = re.fullmatch(r"(\d+\.\d+\.\d+)-rc\.\d+", VERSION)
    if expected_rc and observed_beta and observed_beta.group(1) == "0.1.0" and expected_rc.group(1) == "1.0.0":
        return Compatibility("current", VERSION, observed_version, AGENT_API_CONTRACT, observed_contract, "legacy beta release line is compatible with the 1.0.0 RC API contract")
    expected_stable = re.fullmatch(r"(\d+\.\d+\.\d+)", VERSION)
    observed_rc = re.fullmatch(r"(\d+\.\d+\.\d+)-rc\.\d+", observed_version)
    if expected_stable and observed_rc and observed_rc.group(1) == expected_stable.group(1):
        return Compatibility("current", VERSION, observed_version, AGENT_API_CONTRACT, observed_contract, "release-candidate agent is compatible with the stable API contract")
    if expected_stable and observed_beta and expected_stable.group(1) in {"1.0.0", "1.0.1"} and observed_beta.group(1) == "0.1.0":
        return Compatibility("current", VERSION, observed_version, AGENT_API_CONTRACT, observed_contract, "legacy beta agent is compatible with the stable API contract")
    if VERSION == "1.0.1" and observed_version == "1.0.0":
        return Compatibility("current", VERSION, observed_version, AGENT_API_CONTRACT, observed_contract, "previous stable agent is compatible with the 1.0.1 patch release")
    return Compatibility("incompatible", VERSION, observed_version, AGENT_API_CONTRACT, observed_contract, "unsupported agent version")
