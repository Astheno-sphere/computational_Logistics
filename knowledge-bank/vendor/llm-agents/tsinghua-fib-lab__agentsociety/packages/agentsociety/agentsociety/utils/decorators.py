
__all__ = [
    "lock_decorator",
]


def lock_decorator(func):
    async def wrapper(self, *args, **kwargs):
        # uid = str(uuid.uuid4())
        # func_name = func.__name__
        # func_module = func.__module__
        async with self._lock:
            # get_logger().info(f"Lock acquired for {uid} with lock id {id(self._lock)}, function: {func_module}.{func_name}")
            result = await func(self, *args, **kwargs)
            # get_logger().info(f"Lock released for {uid} with lock id {id(self._lock)}, function: {func_module}.{func_name}")
            return result

    return wrapper
