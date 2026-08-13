class OperatorError(RuntimeError):
    """Base failure for a operator action."""


class ValidationError(OperatorError):
    """Local input or policy validation failed."""


class PolicyError(OperatorError):
    """The requested action falls outside the active policy."""


class GraphAPIError(OperatorError):
    """Meta Graph API returned an error."""

    def __init__(
        self,
        message: str,
        *,
        error_code: int | None = None,
        error_subcode: int | None = None,
        is_transient: bool = False,
        fbtrace_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.error_subcode = error_subcode
        self.is_transient = is_transient
        self.fbtrace_id = fbtrace_id

    @property
    def is_hard_ad_account_throttle(self) -> bool:
        return self.error_code == 17 and self.error_subcode == 2446079


class ReadbackError(OperatorError):
    """Post-write state did not match the approved plan."""
