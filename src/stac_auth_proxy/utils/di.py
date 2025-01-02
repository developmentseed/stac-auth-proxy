from fastapi.dependencies.models import Dependant


def has_any_security_requirements(dependency: Dependant) -> bool:
    """
    Recursively check if any dependency within the hierarchy has a non-empty
    security_requirements list.
    """
    if dependency.security_requirements:
        return True
    return any(
        has_any_security_requirements(sub_dep) for sub_dep in dependency.dependencies
    )
