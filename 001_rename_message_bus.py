from stitcher.refactor.migration import MigrationSpec, Rename


def upgrade(spec: MigrationSpec):
    """
    Renames the core MessageBus to FeedbackBus to better reflect its purpose.
    """
    spec.add(
        Rename(
            old_fqn="stitcher.common.messaging.bus.MessageBus",
            new_fqn="stitcher.common.messaging.bus.FeedbackBus",
        )
    )
