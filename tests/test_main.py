import pytest

import tapystry as tap


def test_simple():
    def fn():
        yield tap.Send('key')
        return 5

    assert tap.run(fn) == 5


def test_receive():
    def sender(value):
        yield tap.Send('key', value)

    def receiver():
        value = yield tap.Receive('key')
        return value

    def fn():
        recv_task = yield tap.CallFork(receiver)
        send_task = yield tap.CallFork(sender, 5)
        yield tap.Join(send_task)
        value = yield tap.Join(recv_task)
        # join again should give the same thing, it's already done
        value1 = yield tap.Join(recv_task)
        assert value1 == value
        return value

    assert tap.run(fn) == 5


def test_never_receive():
    def sender(value):
        yield tap.Send('key', value)

    def receiver():
        value = yield tap.Receive('key')
        return value

    def fn():
        # fork in wrong order!
        send_task = yield tap.CallFork(sender, 5)
        recv_task = yield tap.CallFork(receiver)
        yield tap.Join(send_task)
        value = yield tap.Join(recv_task)
        return value

    with pytest.raises(tap.TapystryError) as x:
        tap.run(fn)
    assert str(x.value).startswith("Hanging strands")


def test_bad_yield():
    def fn():
        yield 3

    with pytest.raises(tap.TapystryError) as x:
        tap.run(fn)
    assert str(x.value).startswith("Strand yielded non-effect")


def test_immediate_return():
    def fn():
        if False:
            yield
        return 3

    assert tap.run(fn) == 3


def test_never_join():
    def sender(value):
        yield tap.Send('key', value)
        yield tap.Send('key2', value)

    def fn():
        yield tap.CallFork(sender, 5)
        return

    assert tap.run(fn) is None


def test_no_arg():
    def sender(value):
        yield tap.Send('key', value)

    def fn():
        yield tap.CallFork(sender)
        return

    with pytest.raises(TypeError):
        tap.run(fn)


def test_call():
    def random(value):
        yield tap.Send('key', value)
        return 10

    def fn():
        x = yield tap.Call(random, 5)
        return x

    assert tap.run(fn) == 10


def test_cancel():
    a = 0
    def add_three(value):
        nonlocal a
        yield tap.Receive('key')
        a += 5
        yield tap.Receive('key')
        a += 5
        yield tap.Receive('key')
        a += 5
        return 10

    def fn():
        task = yield tap.CallFork(add_three, 5)
        yield tap.Send('key')
        yield tap.Send('key')
        yield tap.Cancel(task)

    tap.run(fn)
    assert a == 10


def test_multifirst():
    def sender(value):
        yield tap.Send('key', value)

    def receiver(wait_value):
        value = yield tap.Receive('key', lambda x: x == wait_value)
        return value

    def fn():
        task_1 = yield tap.CallFork(receiver, 1)
        task_2 = yield tap.CallFork(receiver, 2)
        task_3 = yield tap.CallFork(receiver, 3)
        results = yield tap.Fork([
            tap.First([task_1, task_2, task_3]),
            tap.First([task_2, task_1]),
        ])
        yield tap.Call(sender, 5)
        yield tap.Call(sender, 3)
        yield tap.Call(sender, 1)
        value = yield tap.Join(results)
        return value

    # the first race resolves first, thus cancelling tasks 1 and 2, preventing the second from ever finishing
    with pytest.raises(tap.TapystryError) as x:
        tap.run(fn)
    assert str(x.value).startswith("Hanging strands")


def test_multifirst_again():
    def sender(value):
        yield tap.Send('key', value)

    def receiver(wait_value):
        value = yield tap.Receive('key', lambda x: x == wait_value)
        return value

    def fn():
        task_1 = yield tap.CallFork(receiver, 1)
        task_2 = yield tap.CallFork(receiver, 2)
        task_3 = yield tap.CallFork(receiver, 3)
        results = yield tap.Fork([
            tap.First([task_1, task_2]),
            tap.First([task_2, task_3]),
        ])
        yield tap.Call(sender, 5)
        yield tap.Call(sender, 1)
        yield tap.Call(sender, 3)
        value = yield tap.Join(results)
        return value

    assert tap.run(fn) == [
        (0, 1),
        (1, 3),
    ]