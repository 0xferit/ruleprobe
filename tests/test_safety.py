import ast

from ruleprobe.repo import is_safe_to_execute


def fn(src):
    return next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef))


def test_pure_computation_is_safe():
    assert is_safe_to_execute(fn("def f(a, b):\n    return a + b\n")) is True


def test_function_taking_a_client_is_rejected():
    """The model would be asked to test order placement against a real trading
    library. Nothing about that belongs in an automated local sandbox."""
    assert is_safe_to_execute(fn("def submit(client, amount):\n    return client.submit(amount)\n")) is False


def test_function_taking_a_websocket_is_rejected():
    assert is_safe_to_execute(fn("def f(websocket):\n    return websocket.recv()\n")) is False


def test_function_calling_input_is_rejected():
    """A generated test would block until the run's timeout kills it."""
    assert is_safe_to_execute(fn("def f():\n    return input('ok? ')\n")) is False


def test_network_calls_are_rejected():
    assert is_safe_to_execute(fn("def f(u):\n    return requests.get(u)\n")) is False


def test_subprocess_is_rejected():
    assert is_safe_to_execute(fn("def f(c):\n    return subprocess.run(c)\n")) is False


def test_filesystem_writes_are_rejected():
    assert is_safe_to_execute(fn("def f(p):\n    return open(p, 'w')\n")) is False


def test_reading_a_file_is_still_allowed():
    assert is_safe_to_execute(fn("def f(p):\n    return open(p).read()\n")) is True


def test_a_parameter_merely_containing_a_safe_word_is_not_rejected():
    """`recipient` contains no client surface; substring matching would wrongly
    reject ordinary parameters and silently shrink the task set."""
    assert is_safe_to_execute(fn("def f(recipient, sessions_count):\n    return recipient\n")) is True


from ruleprobe.repo import slice_is_safe

CLIENT_FACTORY_SLICE = '''
from bitfinex_maker_kit.utilities.client_factory import get_client

def cancel_order(order_id):
    """Cancel a specific order by ID - with dependency injection support."""
    client = get_client()
    client.cancel_order(order_id)
    return True
'''

PURE_SLICE = '''
def get_side_from_amount(amount):
    """Return the order side implied by the sign of the amount."""
    return "buy" if amount > 0 else "sell"
'''


def test_slice_acquiring_a_client_internally_is_rejected():
    """The real hazard: no client parameter, so signature inspection sees
    nothing. `cancel_order` in bitfinex-maker-kit calls get_client() in its body
    and would cancel live orders if credentials were present."""
    assert slice_is_safe(CLIENT_FACTORY_SLICE) is False


def test_pure_slice_is_accepted():
    assert slice_is_safe(PURE_SLICE) is True


def test_slice_importing_a_client_module_is_rejected():
    src = "from bitfinex_maker_kit.bitfinex_client import wrap\n\ndef f(x):\n    return wrap(x)\n"
    assert slice_is_safe(src) is False


def test_slice_importing_a_websocket_module_is_rejected():
    src = "from bitfinex_maker_kit.websocket.feed import Feed\n\ndef f():\n    return Feed()\n"
    assert slice_is_safe(src) is False


def test_unparseable_slice_is_rejected_rather_than_assumed_safe():
    assert slice_is_safe("def f(:\n") is False


from ruleprobe.repo import imports_only_stdlib


def test_slice_importing_the_host_package_is_rejected():
    """Structural guarantee: if the trading package is not importable in the
    sandbox, no generated test can reach a client no matter what it writes.
    That is stronger than any filter on what the slice itself does."""
    src = "from bitfinex_maker_kit.domain import Symbol\n\ndef f(x):\n    return Symbol(x)\n"
    assert imports_only_stdlib(src, "bitfinex_maker_kit") is False


def test_stdlib_only_slice_is_accepted():
    src = "import math\nfrom decimal import Decimal\n\ndef f(x):\n    return math.sqrt(x)\n"
    assert imports_only_stdlib(src, "bitfinex_maker_kit") is True
