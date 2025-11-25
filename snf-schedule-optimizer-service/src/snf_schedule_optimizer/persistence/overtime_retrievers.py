import datetime
from typing import Iterable, List, Optional

import pendulum
import sqlalchemy
import sqlalchemy.orm

from snf_schedule_optimizer.models import Employee, OvertimeTrigger, Shift
from snf_schedule_optimizer.services.calculations.overtime_calculation import ThresholdOvertimeRule
from snf_schedule_optimizer.services.interfaces import IOvertimeRule, IOvertimeRuleRetrieverService
from snf_schedule_optimizer.sqlalchemy_models.overtime_rule_config import OvertimeRuleConfig


class SQLAOvertimeRuleRetriever(IOvertimeRuleRetrieverService):
    """
    Concrete implementation of the rule retriever using SQLAlchemy to connect
    to a PostgreSQL database.
    """

    def __init__(self, db_session: sqlalchemy.orm.Session):
        self.db_session = db_session

    def _map_db_record_to_rule(self, record: OvertimeRuleConfig) -> ThresholdOvertimeRule:
        """
        Translates a SQLAlchemy ORM object into the application's ThresholdOvertimeRule object.
        """

        # Helper to convert SQLA Time/Date to pendulum types safely
        def to_pendulum_time(t: Optional[datetime.time]) -> Optional[pendulum.Time]:
            if t is None:
                return None
            return pendulum.time(t.hour, t.minute, t.second)

        # 1. Create the OvertimeTrigger object from the record data
        trigger = OvertimeTrigger(
            daily_threshold=record.daily_threshold,
            weekly_threshold=record.weekly_threshold,

            work_period_start_time=to_pendulum_time(record.work_period_start_time),
            daily_period_reset_time=to_pendulum_time(record.daily_period_reset_time),

            consecutive_day_threshold=record.consecutive_day_threshold,
            consecutive_hours_threshold=record.consecutive_hours_threshold,

            # Assuming days_of_week_trigger is stored as a delimited string or array in the DB
            days_of_week_trigger=[
                pendulum.WeekDay(d)
                for d in record.days_of_week_trigger
            ] if record.days_of_week_trigger is not None else None
        )

        # 2. Create the ThresholdOvertimeRule object
        return ThresholdOvertimeRule(
            name=record.name,
            multiplier=record.multiplier,
            trigger=trigger,
            priority=record.priority,
            applicable_job_titles=record.applicable_job_titles,
        )

    def get_applicable_rules(
            self,
            employee: Employee,
            shift: Shift,
    ) -> List[IOvertimeRule]:

        # 1. Define the base query to fetch all active rules
        stmt = sqlalchemy.select(OvertimeRuleConfig).where(
            # Basic active/date filtering (assuming these fields exist)
            sqlalchemy.and_(
                OvertimeRuleConfig.is_active == True,
                OvertimeRuleConfig.effective_date <= shift.shift_start_dt.date(),
            )
        )

        # 2. Add Eligibility Filtering (Database Optimization)
        # Filter by employee's union or contract ID if the DB model supports it
        if hasattr(employee, 'union_contract_id'):
            stmt = stmt.where(
                sqlalchemy.and_(
                    OvertimeRuleConfig.union_contract_id == employee.union_contract_id,
                    # OR rules applicable to all
                    OvertimeRuleConfig.union_contract_id.is_(None)
                )
            )

        # 3. Execute Query and Map Results
        db_records: Iterable[OvertimeRuleConfig] = self.db_session.execute(stmt).scalars().all()

        # 4. Final Rule Instantiation and In-Memory Eligibility Check
        applicable_rules: List[IOvertimeRule] = []
        for record in db_records:
            rule = self._map_db_record_to_rule(record)
            applicable_rules.append(rule)

        # 5. Sort by Priority (Highest priority rules processed first)
        # This is important for the OvertimeCalculator when breaking ties
        return sorted(applicable_rules, key=lambda r: r.priority, reverse=True)
