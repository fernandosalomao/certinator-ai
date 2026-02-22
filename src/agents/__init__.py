"""Certinator AI — Agent configuration package."""

from .certification_info_agent import (
    INSTRUCTIONS as CERT_INFO_INSTRUCTIONS,
)
from .certification_info_agent import (
    create_cert_info_agent,
)
from .coordinator_agent import (
    INSTRUCTIONS as COORDINATOR_INSTRUCTIONS,
)
from .coordinator_agent import (
    create_coordinator_agent,
)
from .critic_agent import (
    INSTRUCTIONS as CRITIC_INSTRUCTIONS,
)
from .critic_agent import (
    create_critic_agent,
)
from .learning_path_fetcher_agent import (
    INSTRUCTIONS as LEARNING_PATH_FETCHER_INSTRUCTIONS,
)
from .learning_path_fetcher_agent import (
    create_learning_path_fetcher_agent,
)
from .practice_questions_agent import (
    INSTRUCTIONS as PRACTICE_INSTRUCTIONS,
)
from .practice_questions_agent import (
    create_practice_agent,
)
from .study_plan_generator_agent import (
    INSTRUCTIONS as STUDY_PLAN_INSTRUCTIONS,
)
from .study_plan_generator_agent import (
    create_study_plan_agent,
)

__all__ = [
    "CERT_INFO_INSTRUCTIONS",
    "COORDINATOR_INSTRUCTIONS",
    "CRITIC_INSTRUCTIONS",
    "LEARNING_PATH_FETCHER_INSTRUCTIONS",
    "PRACTICE_INSTRUCTIONS",
    "STUDY_PLAN_INSTRUCTIONS",
    "create_cert_info_agent",
    "create_coordinator_agent",
    "create_critic_agent",
    "create_learning_path_fetcher_agent",
    "create_practice_agent",
    "create_study_plan_agent",
]
