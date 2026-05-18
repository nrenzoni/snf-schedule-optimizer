"""Proto-to-domain validation layer — ensures domain invariants are enforced at the boundary."""

from dataclasses import dataclass

from snf_schedule_optimizer.models import (
    OptimizationSettings,
    Schedule,
    StagedSchedulePatch,
)


@dataclass(frozen=True)
class ValidationResult:
    is_valid: bool
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


class ProtoToDomainValidator:
    """Validates proto inputs before they enter the domain layer."""

    def validate_optimization_settings(
        self, settings: OptimizationSettings
    ) -> ValidationResult:
        errors: list[str] = []

        if settings.min_rest_period > settings.max_shift_length:
            errors.append(
                f"min_rest_period ({settings.min_rest_period}) cannot exceed "
                f"max_shift_length ({settings.max_shift_length})"
            )

        if settings.buffer_threshold < 0:
            errors.append("buffer_threshold must be non-negative")

        if settings.overtime_avoidance_penalty < 0:
            errors.append("overtime_avoidance_penalty must be non-negative")

        if settings.team_consistency_penalty < 0:
            errors.append("team_consistency_penalty must be non-negative")

        if settings.high_risk_shift_penalty < 0:
            errors.append("high_risk_shift_penalty must be non-negative")

        if settings.custom_preference_penalty < 0:
            errors.append("custom_preference_penalty must be non-negative")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=tuple(errors),
        )

    def validate_patches_against_schedule(
        self, patches: tuple[StagedSchedulePatch, ...], schedule: Schedule
    ) -> ValidationResult:
        """Validate that staged patches are consistent with the current schedule version."""
        errors: list[str] = []
        warnings: list[str] = []

        for patch in patches:
            if patch.to_shift_id is not None:
                shift_key = None
                for key in schedule.shift_assignments:
                    if key.shift_id == patch.to_shift_id:
                        shift_key = key
                        break
                if shift_key is None:
                    errors.append(
                        f"Patch {patch.patch_id}: target shift {patch.to_shift_id} "
                        f"not found in schedule"
                    )

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=tuple(errors),
            warnings=tuple(warnings),
        )


validator = ProtoToDomainValidator()
