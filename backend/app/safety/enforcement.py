HIGH_IMPACT_ACTIONS = frozenset(
    {
        "restart",
        "rollback",
        "scale",
        "modify_config",
        "delete_resource",
        "recreate",
    }
)


def requires_approval(action_type: str | None) -> bool:
    if not action_type:
        return False
    return action_type.lower() in HIGH_IMPACT_ACTIONS
