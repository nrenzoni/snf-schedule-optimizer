"""
Client Deployment & Versioning: Manages which version of your optimization model is deployed to which client, allowing you to A/B test different strategies across different facilities.
"""

from snf_schedule_optimizer.models import DomainPrimaryKeyType


def deploy_model_version(
    facility_id: DomainPrimaryKeyType,
    model_version_id: DomainPrimaryKeyType,
) -> None:
    pass
