"""MOCK ONLY: LS Login's rules for token exchange, which the mock doesn't enforce.

`mock-oauth2-server` exchanges anything. These checks make a local run behave
like LS Login as the LS Login team described it on 2026-11-03. They run in the
testbed, in front of the mock, and refusals say so (`refused_by`). A passing
local run therefore shows that our code handles refusals, NOT that LS Login
behaves this way. The checks are never used with LS Login, which decides by
itself. The error codes are the testbed's guess; what LS Login returns is one
of the things to record.
"""

from collections.abc import Sequence

from testbed.settings import Client
from testbed.validation import InvalidToken, TokenValidator

REFUSED_BY_RULE = "testbed rule (mock only; not LS Login)"


class RuleViolation(Exception):
    """An exchange is against LS Login's rules, as the testbed emulates them.

    Attributes:
        error: OAuth 2.0 error code.
        description: Description.
    """

    def __init__(self, error: str, description: str) -> None:
        """Create the exception.

        Args:
            error: OAuth 2.0 error code.
            description: Description.
        """
        super().__init__(f"{error}: {description}")
        self.error = error
        self.description = description


def check_exchange(
    client: Client,
    subject_token: str,
    targets: Sequence[str],
    validator: TokenValidator,
) -> None:
    """Check an exchange against LS Login's rules.

    Args:
        client: Exchanging client.
        subject_token: Subject token.
        targets: Requested audiences and resources.
        validator: Validator with the exchanging client's ID as the only
            accepted audience, as LS Login requires it in the subject token.

    Raises:
        RuleViolation: The exchange is against the rules.
    """
    try:
        validator.validate(subject_token)
    except InvalidToken as exc:
        raise RuleViolation(
            "invalid_grant", f"Subject token refused ({exc.reason}): {exc.detail}"
        ) from exc
    unregistered = [target for target in targets if target not in client.registered]
    if unregistered:
        raise RuleViolation(
            "invalid_target",
            f"Not registered for {client.client_id}: {', '.join(unregistered)}",
        )
