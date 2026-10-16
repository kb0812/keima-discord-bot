import importlib
import pkgutil

import tasks


def get_tasks(bot):
    task_list = [
        importlib.import_module(f"{tasks.__name__}.{name}")
        for _, name, _ in pkgutil.iter_modules(tasks.__path__)
    ]

    ret = []

    for task in task_list:
        ret.append(task.get_task(bot))

    return ret
