"""
AI Engine Module for LIFELINE v5.0.

This module provides two primary subsystems:
1. DonorScreeningEngine: A Knowledge-Based Expert System for evaluating blood donor eligibility.
2. TransfusionMonitorAgent: A Model-Based Reflex Agent for monitoring and detecting adverse transfusion reactions.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List
import pandas as pd


# ==========================================
# SUBSYSTEM 1 — DonorScreeningEngine
# ==========================================

class AbstractScoringStrategy(ABC):
    """
    Abstract base class for donor scoring strategies.
    Implements the Strategy Design Pattern.
    """

    @abstractmethod
    def score(self, donor_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluates donor data and returns a scoring dictionary.

        Args:
            donor_data (Dict[str, Any]): Dictionary containing donor details.

        Returns:
            Dict[str, Any]: Evaluation result containing final score, classification,
                            penalties, and recommendation.
        """
        pass


class RuleBasedStrategy(AbstractScoringStrategy):
    """
    Rule-based strategy using a Python dictionary as a Knowledge Base (KB).
    Applies forward-chaining inference to deduct risk points.
    """

    def score(self, donor_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculates donor score using predefined logical rules.

        Args:
            donor_data (Dict[str, Any]): Donor information including age, weight,
                                         blood pressure, diseases, etc.

        Returns:
            Dict[str, Any]: Scoring report.
        """
        score = 100
        penalties = []

        # Safe extraction
        age = int(donor_data.get('age', 0))
        on_blood_thinners = bool(donor_data.get('on_blood_thinners', False))
        days_since_last_donation = int(donor_data.get('days_since_last_donation', 999))
        diseases = donor_data.get('diseases', [])
        weight = float(donor_data.get('weight', 0.0))
        systolic_bp = int(donor_data.get('systolic_bp', 120))
        diastolic_bp = int(donor_data.get('diastolic_bp', 80))

        # Apply rules
        if age < 18 or age > 65:
            penalties.append({"rule": "Age", "deduction": 20, "reason": "Age outside safe donation range"})
        
        if on_blood_thinners:
            penalties.append({"rule": "Medication", "deduction": 30, "reason": "Anticoagulant medication detected"})
            
        if days_since_last_donation < 90:
            penalties.append({"rule": "Donation Interval", "deduction": 15, "reason": "Insufficient recovery period (<90 days)"})
            
        if 'Diabetes' in diseases:
            penalties.append({"rule": "Condition", "deduction": 10, "reason": "Controlled chronic condition (Diabetes)"})
            
        if 'Hypertension' in diseases:
            penalties.append({"rule": "Condition", "deduction": 10, "reason": "Controlled chronic condition (Hypertension)"})
            
        if any(d in diseases for d in ['HepB', 'HepC', 'HIV']):
            penalties.append({"rule": "Pathogen", "deduction": 100, "reason": "Transmissible bloodborne pathogen — BLOCKED"})
            
        if weight < 50:
            penalties.append({"rule": "Weight", "deduction": 20, "reason": "Body weight below minimum threshold (50kg)"})
            
        if systolic_bp > 160 or diastolic_bp > 100:
            penalties.append({"rule": "Blood Pressure", "deduction": 15, "reason": "Hypertensive blood pressure reading"})

        for penalty in penalties:
            score -= penalty["deduction"]
        
        # Ensure score does not drop below 0
        score = max(0, score)

        if score >= 80:
            classification = "SAFE"
            recommendation = "Donor is healthy and eligible for blood donation."
        elif 50 <= score < 80:
            classification = "CAUTION"
            recommendation = "Proceed with caution. Additional medical evaluation recommended."
        else:
            classification = "BLOCKED"
            recommendation = "Donor is ineligible. Do not proceed with donation."

        return {
            "final_score": int(score),
            "classification": classification,
            "penalties": penalties,
            "recommendation": recommendation
        }


class WeightedMLStrategy(AbstractScoringStrategy):
    """
    Pandas-based scoring strategy that applies configurable weight multipliers per rule.
    Serves as a foundation for future integration with Machine Learning models.
    """

    def __init__(self, weight_multiplier: float = 1.0):
        """
        Initializes the ML strategy.

        Args:
            weight_multiplier (float): Multiplier applied to penalty deductions.
        """
        self.weight_multiplier = weight_multiplier

    def score(self, donor_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculates donor score by processing tabular data using pandas.

        Args:
            donor_data (Dict[str, Any]): Donor information.

        Returns:
            Dict[str, Any]: Scoring report.
        """
        # Convert to pandas DataFrame for tabular handling
        df = pd.DataFrame([donor_data])
        row = df.iloc[0]
        
        score = 100.0
        penalties = []

        # Extract values via pandas and cast to pure Python types for JSON serialization
        age = int(row.get('age', 0))
        on_blood_thinners = bool(row.get('on_blood_thinners', False))
        days_since_last_donation = int(row.get('days_since_last_donation', 999))
        
        diseases = row.get('diseases', [])
        # Handle cases where diseases could be NaN or un-iterable from DataFrame
        if isinstance(diseases, str):
            diseases = [diseases]
        elif isinstance(diseases, float) and pd.isna(diseases):
            diseases = []
        else:
            try:
                diseases = list(diseases)
            except TypeError:
                diseases = []
            
        weight = float(row.get('weight', 0.0))
        systolic_bp = int(row.get('systolic_bp', 120))
        diastolic_bp = int(row.get('diastolic_bp', 80))

        # Apply rules with ML weights
        if age < 18 or age > 65:
            penalties.append({"rule": "Age", "deduction": int(20 * self.weight_multiplier), "reason": "Age outside safe donation range"})
        
        if on_blood_thinners:
            penalties.append({"rule": "Medication", "deduction": int(30 * self.weight_multiplier), "reason": "Anticoagulant medication detected"})
            
        if days_since_last_donation < 90:
            penalties.append({"rule": "Donation Interval", "deduction": int(15 * self.weight_multiplier), "reason": "Insufficient recovery period (<90 days)"})
            
        if 'Diabetes' in diseases:
            penalties.append({"rule": "Condition", "deduction": int(10 * self.weight_multiplier), "reason": "Controlled chronic condition (Diabetes)"})
            
        if 'Hypertension' in diseases:
            penalties.append({"rule": "Condition", "deduction": int(10 * self.weight_multiplier), "reason": "Controlled chronic condition (Hypertension)"})
            
        if any(d in diseases for d in ['HepB', 'HepC', 'HIV']):
            penalties.append({"rule": "Pathogen", "deduction": int(100 * self.weight_multiplier), "reason": "Transmissible bloodborne pathogen — BLOCKED"})
            
        if weight < 50:
            penalties.append({"rule": "Weight", "deduction": int(20 * self.weight_multiplier), "reason": "Body weight below minimum threshold (50kg)"})
            
        if systolic_bp > 160 or diastolic_bp > 100:
            penalties.append({"rule": "Blood Pressure", "deduction": int(15 * self.weight_multiplier), "reason": "Hypertensive blood pressure reading"})

        for penalty in penalties:
            score -= penalty["deduction"]
        
        score = max(0.0, float(score))

        if score >= 80:
            classification = "SAFE"
            recommendation = "Donor is healthy and eligible for blood donation."
        elif 50 <= score < 80:
            classification = "CAUTION"
            recommendation = "Proceed with caution. Additional medical evaluation recommended."
        else:
            classification = "BLOCKED"
            recommendation = "Donor is ineligible. Do not proceed with donation."

        return {
            "final_score": int(score),
            "classification": classification,
            "penalties": penalties,
            "recommendation": recommendation
        }


class DonorScreeningEngine:
    """
    Expert System orchestrator that delegates screening to an injected strategy.
    """

    def __init__(self, strategy: AbstractScoringStrategy):
        """
        Initializes the screening engine.

        Args:
            strategy (AbstractScoringStrategy): The scoring strategy to utilize.
        """
        self.strategy = strategy

    def evaluate_donor(self, donor_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluates a donor based on the configured strategy.

        Args:
            donor_data (Dict[str, Any]): The donor's medical and demographic data.

        Returns:
            Dict[str, Any]: JSON-serializable evaluation result.
        """
        return self.strategy.score(donor_data)


# ==========================================
# SUBSYSTEM 2 — TransfusionMonitorAgent
# ==========================================

class TransfusionMonitorAgent:
    """
    Model-Based Reflex Agent that monitors pre and post transfusion vitals
    to detect critical reactions and trigger actions deterministically.
    """

    def analyze(self, pre: Dict[str, float], post: Dict[str, float]) -> Dict[str, Any]:
        """
        Analyzes vitals before and after transfusion to detect adverse reactions.

        Args:
            pre (Dict[str, float]): Vitals before transfusion containing bp_sys, bp_dia,
                                    pulse, temp_c, o2_sat.
            post (Dict[str, float]): Vitals after/during transfusion containing the same keys.

        Returns:
            Dict[str, Any]: JSON-serializable reaction analysis report.
        """
        # Calculate deltas utilizing raw standard floats
        temp_rise = float(post.get('temp_c', 37.0)) - float(pre.get('temp_c', 37.0))
        bp_drop = float(pre.get('bp_sys', 120.0)) - float(post.get('bp_sys', 120.0))
        pulse_rise = float(post.get('pulse', 80.0)) - float(pre.get('pulse', 80.0))
        o2_drop = float(pre.get('o2_sat', 98.0)) - float(post.get('o2_sat', 98.0))
        o2_sat_post = float(post.get('o2_sat', 98.0))

        reaction = "NORMAL"
        severity = "NORMAL"
        action = "Continue monitoring as scheduled. No immediate intervention required."

        if temp_rise > 2.0 and bp_drop > 30.0:
            reaction = "HEMOLYTIC_REACTION"
            severity = "CRITICAL"
            action = "STOP TRANSFUSION IMMEDIATELY! Keep IV line open with saline. Notify physician and blood bank."
        elif bp_drop > 40.0 and o2_drop > 10.0:
            reaction = "ANAPHYLAXIS"
            severity = "CRITICAL"
            action = "STOP TRANSFUSION IMMEDIATELY! Administer epinephrine and airway support. Notify physician."
        elif temp_rise > 1.0 and pulse_rise > 30.0:
            reaction = "FEBRILE_REACTION"
            severity = "WARNING"
            action = "PAUSE TRANSFUSION. Administer antipyretics per protocol and notify physician."
        elif o2_sat_post < 90.0:
            reaction = "HYPOXIA_ALERT"
            severity = "WARNING"
            action = "Provide supplemental oxygen. Elevate head of bed and notify physician."

        return {
            "reaction": reaction,
            "severity": severity,
            "action": action,
            "deltas": {
                "temp_rise": round(temp_rise, 2),
                "bp_drop": round(bp_drop, 2),
                "pulse_rise": round(pulse_rise, 2),
                "o2_drop": round(o2_drop, 2),
                "o2_sat_post": round(o2_sat_post, 2)
            }
        }


# ==========================================
# DEMONSTRATION BLOCK
# ==========================================

if __name__ == "__main__":
    import json
    
    print("=== LIFELINE v5.0 AI Subsystems Demo ===\n")
    
    # Realistic Pakistani hospital data matching lifeline.db schema
    donor_1 = {
        "donor_id": "D-PK-001",
        "name": "Ahmed Khan",
        "blood_group": "O+",
        "age": 34,
        "weight": 72.5,
        "systolic_bp": 125,
        "diastolic_bp": 82,
        "diseases": [],
        "on_blood_thinners": False,
        "days_since_last_donation": 120
    }
    
    donor_2 = {
        "donor_id": "D-PK-002",
        "name": "Fatima Ali",
        "blood_group": "A-",
        "age": 45,
        "weight": 68.0,
        "systolic_bp": 140,
        "diastolic_bp": 90,
        "diseases": ["Diabetes"],
        "on_blood_thinners": False,
        "days_since_last_donation": 45
    }
    
    donor_3 = {
        "donor_id": "D-PK-003",
        "name": "Usman Tariq",
        "blood_group": "B+",
        "age": 28,
        "weight": 55.0,
        "systolic_bp": 118,
        "diastolic_bp": 78,
        "diseases": ["HepB"],
        "on_blood_thinners": False,
        "days_since_last_donation": 200
    }

    print("--- Subsystem 1: Donor Screening Engine ---")
    engine_rule_based = DonorScreeningEngine(RuleBasedStrategy())
    engine_ml_based = DonorScreeningEngine(WeightedMLStrategy(weight_multiplier=1.2))
    
    for i, d in enumerate([donor_1, donor_2, donor_3], 1):
        print(f"\nEvaluating Donor {i} ({d['name']}) with RuleBasedStrategy:")
        result = engine_rule_based.evaluate_donor(d)
        print(json.dumps(result, indent=2))
        
        print(f"Evaluating Donor {i} ({d['name']}) with WeightedMLStrategy (1.2x penalty):")
        result_ml = engine_ml_based.evaluate_donor(d)
        print(json.dumps(result_ml, indent=2))

    print("\n--- Subsystem 2: Transfusion Monitor Agent ---")
    monitor = TransfusionMonitorAgent()
    
    pre_vitals = {
        "bp_sys": 120.0,
        "bp_dia": 80.0,
        "pulse": 75.0,
        "temp_c": 36.8,
        "o2_sat": 99.0
    }
    
    # Simulated Hemolytic Reaction
    post_vitals_hemolytic = {
        "bp_sys": 85.0,
        "bp_dia": 60.0,
        "pulse": 110.0,
        "temp_c": 39.1,
        "o2_sat": 95.0
    }
    
    print("\nScenario: Hemolytic Reaction Detected")
    reaction_report = monitor.analyze(pre_vitals, post_vitals_hemolytic)
    print(json.dumps(reaction_report, indent=2))
