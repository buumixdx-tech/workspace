"""
规则评估器模块

职责：
1. 计算 flag_time (根据触发事件 + 偏移量)
2. 评估规则是否合规
3. 生成告警等级
4. 更新规则状态
"""

from datetime import datetime, timedelta
from typing import Optional

from models import get_session, TimeRule
from logic.constants import (
    EventType, TimeRuleOffsetUnit, TimeRuleDirection, 
    TimeRuleWarning, TimeRuleStatus, TimeRuleResult
)
from logic.time_rules.event_handler import EventHandler


class RuleEvaluator:
    """
    规则评估器
    
    核心计算引擎，负责：
    - 根据触发事件 + 偏移量计算 flag_time
    - 检查目标事件是否发生
    - 判断是否合规
    - 计算告警等级
    - 更新规则状态
    """
    
    def __init__(self, session=None):
        self.session = session or get_session()
        self.event_handler = EventHandler(self.session)
    
    def evaluate_rule(self, rule: TimeRule) -> dict:
        """
        评估单条规则
        
        Args:
            rule: 待评估的时间规则
        
        Returns:
            {
                'flag_time': datetime or None,
                'trigger_time': datetime or None,
                'target_time': datetime or None,
                'is_compliant': bool or None,
                'warning_level': str,
                'new_status': str,
                'result': str or None
            }
        """
        result = {
            'flag_time': rule.flag_time,
            'trigger_time': rule.trigger_time,
            'target_time': rule.target_time,
            'is_compliant': None,
            'warning_level': TimeRuleWarning.GREEN,
            'new_status': rule.status,
            'result': rule.result
        }
        
        # Step 1: 处理触发事件，计算 flag_time
        if rule.trigger_event == EventType.Special.ABSOLUTE_DATE:
            # 绝对日期模式：flag_time 已在创建时赋值，无需计算
            result['trigger_time'] = None
        elif rule.trigger_event and not rule.flag_time:
            # 标准模式：查询触发事件时间，计算 flag_time
            trigger_time = self.event_handler.get_event_time(
                rule.trigger_event, 
                rule.related_type, 
                rule.related_id,
                rule.tge_param1, 
                rule.tge_param2
            )
            if trigger_time:
                result['trigger_time'] = trigger_time
                rule.trigger_time = trigger_time
                
                # 计算 flag_time
                calculated_flag_time = self._calculate_flag_time(
                    trigger_time, rule.offset, rule.unit
                )
                result['flag_time'] = calculated_flag_time
                rule.flag_time = calculated_flag_time
        
        # Step 2: 检查目标事件
        target_time = self.event_handler.get_event_time(
            rule.target_event,
            rule.related_type,
            rule.related_id,
            rule.tae_param1,
            rule.tae_param2
        )
        if target_time:
            result['target_time'] = target_time
            rule.target_time = target_time
        
        # Step 3: 评估合规性 (仅当 flag_time 和 target_time 都存在时)
        if result['flag_time'] and result['target_time']:
            is_compliant = self._check_compliance(
                result['target_time'], 
                result['flag_time'], 
                rule.direction
            )
            result['is_compliant'] = is_compliant
            result['result'] = (
                TimeRuleResult.COMPLIANT if is_compliant 
                else TimeRuleResult.VIOLATION
            )
            rule.result = result['result']
        
        # Step 4: 更新规则状态
        new_status = self._determine_status(rule, result)
        result['new_status'] = new_status
        
        # Step 5: 计算告警等级 (仅当目标事件未发生时)
        if not result['target_time'] and result['flag_time']:
            warning_level = self._calculate_warning_level(
                result['flag_time'], 
                rule.direction
            )
            result['warning_level'] = warning_level
            rule.warning = warning_level
        elif result['target_time']:
            # 目标事件已发生，无需告警
            result['warning_level'] = TimeRuleWarning.GREEN
            rule.warning = TimeRuleWarning.GREEN
        
        return result
    
    def _calculate_flag_time(self, trigger_time: datetime, 
                              offset: int, unit: str) -> datetime:
        """
        基于触发时间 + 偏移量计算标杆时间
        
        Args:
            trigger_time: 触发事件发生时间
            offset: 偏移量 (可为负数，表示之前)
            unit: 单位 (自然日/工作日)
        
        Returns:
            计算后的标杆时间
        """
        if offset is None:
            offset = 0
        
        if unit == TimeRuleOffsetUnit.WORK_DAY:
            return self._add_work_days(trigger_time, offset)
        elif unit == TimeRuleOffsetUnit.HOUR:
            return trigger_time + timedelta(hours=offset)
        else:
            # 默认使用自然日
            return trigger_time + timedelta(days=offset)
    
    def _add_work_days(self, start_date: datetime, days: int) -> datetime:
        """
        添加工作日（排除周末）
        
        Args:
            start_date: 起始日期
            days: 工作日数量 (正数往后，负数往前)
        
        Returns:
            添加工作日后的日期
        
        TODO: 扩展支持节假日排除
        """
        if days == 0:
            return start_date
        
        current = start_date
        added = 0
        direction = 1 if days >= 0 else -1
        target_days = abs(days)
        
        while added < target_days:
            current += timedelta(days=direction)
            # 周一到周五为工作日 (weekday: 0-4)
            if current.weekday() < 5:
                added += 1
        
        return current
    
    def _check_compliance(self, target_time: datetime, 
                           flag_time: datetime, direction: str) -> bool:
        """
        检查目标事件是否合规
        
        Args:
            target_time: 目标事件发生时间
            flag_time: 标杆时间
            direction: 方向 (before/after)
        
        Returns:
            True 表示合规，False 表示违规
        """
        if direction == TimeRuleDirection.BEFORE:
            # 目标事件需在标杆时间之前（或当天）
            return target_time <= flag_time
        else:  # AFTER
            # 目标事件需在标杆时间之后（或当天）
            return target_time >= flag_time
    
    def _calculate_warning_level(self, flag_time: datetime, 
                                  direction: str) -> str:
        """
        计算告警等级
        
        仅当 direction=BEFORE 时产生紧迫性告警
        
        Args:
            flag_time: 标杆时间
            direction: 方向
        
        Returns:
            告警等级 (绿色/黄色/橙色/红色)
        """
        now = datetime.now()
        
        if direction == TimeRuleDirection.BEFORE:
            # 目标需在 flag_time 之前完成，计算还剩多少天
            delta_days = (flag_time - now).days
            
            if delta_days < 0:
                # 已超时
                return TimeRuleWarning.RED
            elif delta_days <= TimeRuleWarning.THRESHOLDS[TimeRuleWarning.ORANGE]:
                # 1天以内
                return TimeRuleWarning.ORANGE
            elif delta_days <= TimeRuleWarning.THRESHOLDS[TimeRuleWarning.YELLOW]:
                # 3天以内
                return TimeRuleWarning.YELLOW
            else:
                return TimeRuleWarning.GREEN
        else:
            # direction=AFTER 时，一般不产生紧迫性告警
            return TimeRuleWarning.GREEN
    
    def _determine_status(self, rule: TimeRule, eval_result: dict) -> str:
        """
        确定规则状态
        
        状态流转逻辑：
        - 绝对日期模式：目标发生即结束
        - 标准模式：
            - 目标 + 触发都发生 → 结束
            - 目标发生，触发未发生 → 有结果
            - 其他 → 生效
        
        Args:
            rule: 规则对象
            eval_result: 评估结果
        
        Returns:
            新状态
        """
        # 如果已手动失效，保持失效状态
        if rule.status == TimeRuleStatus.INACTIVE:
            return TimeRuleStatus.INACTIVE
        
        target_occurred = eval_result['target_time'] is not None
        
        # 绝对日期模式：无触发事件，目标发生即结束
        if rule.trigger_event == EventType.Special.ABSOLUTE_DATE:
            if target_occurred:
                return TimeRuleStatus.ENDED
            else:
                return TimeRuleStatus.ACTIVE
        
        # 标准模式
        trigger_occurred = eval_result['trigger_time'] is not None or rule.trigger_event is None
        
        if target_occurred and trigger_occurred:
            return TimeRuleStatus.ENDED
        elif target_occurred and not trigger_occurred:
            return TimeRuleStatus.HAS_RESULT
        else:
            return TimeRuleStatus.ACTIVE
