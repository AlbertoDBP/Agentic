"""
NAV Erosion Sustainability Score Integration

Integrates Monte Carlo NAV erosion analysis into Agent 3's Sustainability
scoring component with graduated penalty system.
"""

from typing import Dict, Optional
from datetime import datetime, timedelta
import json


class NAVErosionSustainabilityIntegration:
    """
    Calculates sustainability score penalties based on NAV erosion analysis.
    
    Penalty system:
    - 0-5 points: Low risk (probability <30% for >5% erosion)
    - 5-15 points: Medium risk (probability 30-70%)
    - 15-30 points: High/severe risk (probability >70% or median NAV change <-5%)
    """
    
    def __init__(self, db_connection=None):
        self.db = db_connection
    
    def calculate_sustainability_penalty(
        self,
        erosion_analysis: Dict,
        asset_class: str
    ) -> Dict:
        """
        Calculate penalty to Sustainability score based on erosion probability.
        
        Args:
            erosion_analysis: Results from Monte Carlo simulation
            asset_class: Asset class of the security
        
        Returns:
            Dictionary with:
            - penalty_points: Points to deduct (0-30)
            - rationale: Human-readable explanation
            - severity: Classification (none/low/medium/high/severe)
            - details: Detailed metrics
        """
        # Extract key metrics
        prob_erosion_5pct = erosion_analysis['probability_annual_erosion_gt_5pct']
        prob_erosion_10pct = erosion_analysis['probability_annual_erosion_gt_10pct']
        median_nav_change = erosion_analysis['median_annualized_nav_change_pct']
        prob_any_erosion = erosion_analysis['probability_any_erosion']
        
        # Initialize penalty calculation
        penalty = 0.0
        severity = "none"
        rationale_parts = []
        
        # Penalty Tier 1: High probability of moderate erosion (>5%)
        if prob_erosion_5pct > 70:
            penalty += 15
            severity = "high"
            rationale_parts.append(
                f"{prob_erosion_5pct:.0f}% probability of >5% annual NAV erosion"
            )
        elif prob_erosion_5pct > 50:
            penalty += 10
            severity = "medium"
            rationale_parts.append(
                f"{prob_erosion_5pct:.0f}% probability of >5% annual NAV erosion"
            )
        elif prob_erosion_5pct > 30:
            penalty += 5
            severity = "low"
            rationale_parts.append(
                f"{prob_erosion_5pct:.0f}% probability of >5% annual NAV erosion"
            )
        
        # Penalty Tier 2: Severe erosion risk (>10%)
        if prob_erosion_10pct > 30:
            penalty += 15
            severity = "severe"
            rationale_parts.append(
                f"{prob_erosion_10pct:.0f}% probability of >10% annual NAV erosion (severe)"
            )
        elif prob_erosion_10pct > 15:
            penalty += 8
            if severity not in ["severe", "high"]:
                severity = "high"
            rationale_parts.append(
                f"{prob_erosion_10pct:.0f}% probability of >10% annual NAV erosion"
            )
        elif prob_erosion_10pct > 5:
            penalty += 3
            if severity == "none":
                severity = "low"
            rationale_parts.append(
                f"{prob_erosion_10pct:.0f}% probability of >10% annual NAV erosion"
            )
        
        # Penalty Tier 3: Negative median NAV change (expected erosion)
        if median_nav_change < -5:
            penalty += 10
            severity = "severe"
            rationale_parts.append(
                f"Median projected NAV change: {median_nav_change:.1f}% annually (severe decline)"
            )
        elif median_nav_change < -2:
            penalty += 5
            if severity == "none":
                severity = "medium"
            rationale_parts.append(
                f"Median projected NAV change: {median_nav_change:.1f}% annually"
            )
        elif median_nav_change < 0:
            penalty += 2
            if severity == "none":
                severity = "low"
            rationale_parts.append(
                f"Median projected NAV change: {median_nav_change:.1f}% annually"
            )
        
        # Cap total penalty at 30 points
        penalty = min(penalty, 30)
        
        # Build rationale string
        if not rationale_parts:
            rationale = "Monte Carlo analysis shows low NAV erosion risk"
            severity = "none"
        else:
            rationale = "NAV erosion concerns: " + "; ".join(rationale_parts)
        
        return {
            'penalty_points': round(penalty, 2),
            'rationale': rationale,
            'severity': severity,
            'details': {
                'prob_erosion_5pct': round(prob_erosion_5pct, 1),
                'prob_erosion_10pct': round(prob_erosion_10pct, 1),
                'prob_any_erosion': round(prob_any_erosion, 1),
                'median_nav_change': round(median_nav_change, 2),
                'asset_class': asset_class,
                'var_95': round(erosion_analysis.get('var_95_annualized_pct', 0), 2),
                'var_99': round(erosion_analysis.get('var_99_annualized_pct', 0), 2)
            },
            'analysis_metadata': {
                'simulation_count': erosion_analysis['simulation_params']['n_simulations'],
                'simulation_years': erosion_analysis['simulation_params']['years'],
                'analyzed_at': datetime.utcnow().isoformat()
            }
        }
    
    def should_run_analysis(self, ticker: str, asset_class: str, metadata: Dict = None) -> bool:
        """
        Determine if NAV erosion analysis is needed for this security.
        
        Args:
            ticker: Security ticker
            asset_class: Detected asset class
            metadata: Additional security metadata
        
        Returns:
            True if analysis should be run
        """
        # Asset class triggers
        if asset_class in ['COVERED_CALL_ETF', 'EQUITY_CEF']:
            return True
        
        # Known covered call ETF tickers
        covered_call_tickers = {
            'JEPI', 'JEPQ', 'QYLD', 'XYLD', 'RYLD', 'DIVO', 'SVOL',
            'NUSI', 'QQQI', 'JEPY', 'DJIA', 'IWMY', 'SPYI'
        }
        
        if ticker in covered_call_tickers:
            return True
        
        # Check metadata for covered call strategy
        if metadata:
            strategy = metadata.get('strategy', '').lower()
            fund_type = metadata.get('fund_type', '').lower()
            
            if 'covered call' in strategy or 'option income' in strategy:
                return True
            
            # High distribution yield might indicate covered call strategy
            distribution_yield = metadata.get('distribution_yield_ttm', 0)
            if distribution_yield > 0.10:  # >10% yield
                # Check if it's a CEF or ETF
                if 'cef' in fund_type or 'etf' in fund_type:
                    return True
        
        return False
    
    def get_cached_analysis(
        self,
        ticker: str,
        analysis_type: str = 'quick',
        max_age_days: int = 30
    ) -> Optional[Dict]:
        """
        Retrieve cached NAV erosion analysis if still valid.
        
        Args:
            ticker: Security ticker
            analysis_type: 'quick' or 'deep'
            max_age_days: Maximum age of cache in days
        
        Returns:
            Cached analysis dict or None if not found/expired
        """
        if not self.db:
            return None
        
        query = """
            SELECT 
                simulation_results,
                sustainability_penalty,
                analysis_date,
                valid_until
            FROM nav_erosion_analysis_cache
            WHERE ticker = %s
                AND analysis_type = %s
                AND valid_until >= CURRENT_DATE
            ORDER BY analysis_date DESC
            LIMIT 1
        """
        
        result = self.db.execute_one(query, [ticker.upper(), analysis_type])
        
        if result:
            # Check if cache is fresh enough
            analysis_date = result['analysis_date']
            if isinstance(analysis_date, str):
                analysis_date = datetime.fromisoformat(analysis_date)
            
            age_days = (datetime.now() - analysis_date).days
            
            if age_days <= max_age_days:
                return {
                    'cached': True,
                    'results': result['simulation_results'],
                    'penalty': result['sustainability_penalty'],
                    'cache_age_days': age_days,
                    'analysis_date': analysis_date.isoformat()
                }
        
        return None
    
    def cache_analysis(
        self,
        ticker: str,
        analysis_type: str,
        results: Dict,
        penalty: float,
        valid_days: int = 30
    ):
        """
        Cache NAV erosion analysis results.
        
        Args:
            ticker: Security ticker
            analysis_type: 'quick' or 'deep'
            results: Complete simulation results
            penalty: Calculated sustainability penalty
            valid_days: Number of days cache is valid
        """
        if not self.db:
            return
        
        query = """
            INSERT INTO nav_erosion_analysis_cache
                (ticker, analysis_type, simulation_results, 
                 median_annualized_nav_change_pct, probability_erosion_gt_5pct,
                 probability_erosion_gt_10pct, sustainability_penalty, valid_until)
            VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_DATE + INTERVAL '%s days')
            ON CONFLICT (ticker, analysis_date, analysis_type) 
            DO UPDATE SET 
                simulation_results = EXCLUDED.simulation_results,
                median_annualized_nav_change_pct = EXCLUDED.median_annualized_nav_change_pct,
                probability_erosion_gt_5pct = EXCLUDED.probability_erosion_gt_5pct,
                probability_erosion_gt_10pct = EXCLUDED.probability_erosion_gt_10pct,
                sustainability_penalty = EXCLUDED.sustainability_penalty,
                valid_until = EXCLUDED.valid_until
        """
        
        self.db.execute(
            query,
            [
                ticker.upper(),
                analysis_type,
                json.dumps(results),
                results['median_annualized_nav_change_pct'],
                results['probability_annual_erosion_gt_5pct'],
                results['probability_annual_erosion_gt_10pct'],
                penalty,
                valid_days
            ]
        )
    
    def invalidate_cache(self, ticker: str):
        """
        Invalidate cached analysis for a ticker.
        
        Use when underlying data changes significantly.
        """
        if not self.db:
            return
        
        query = """
            UPDATE nav_erosion_analysis_cache
            SET valid_until = CURRENT_DATE - INTERVAL '1 day'
            WHERE ticker = %s
        """
        
        self.db.execute(query, [ticker.upper()])
    
    def get_penalty_summary_statistics(self, asset_class: str = None) -> Dict:
        """
        Get summary statistics of penalties across securities.
        
        Useful for monitoring and calibration.
        """
        if not self.db:
            return {}
        
        query = """
            SELECT 
                asset_class,
                COUNT(*) as security_count,
                AVG(sustainability_penalty) as avg_penalty,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY sustainability_penalty) as median_penalty,
                MIN(sustainability_penalty) as min_penalty,
                MAX(sustainability_penalty) as max_penalty,
                AVG(probability_erosion_gt_5pct) as avg_prob_5pct,
                AVG(median_annualized_nav_change_pct) as avg_nav_change
            FROM nav_erosion_analysis_cache nac
            JOIN income_scores isc ON nac.ticker = isc.ticker
            WHERE nac.valid_until >= CURRENT_DATE
        """
        
        if asset_class:
            query += " AND isc.asset_class = %s"
            params = [asset_class]
        else:
            params = []
        
        query += " GROUP BY asset_class ORDER BY security_count DESC"
        
        results = self.db.execute_all(query, params) if params else self.db.execute_all(query)
        
        return {
            'by_asset_class': [dict(r) for r in results],
            'generated_at': datetime.utcnow().isoformat()
        }


class NAVErosionRiskClassifier:
    """
    Classifies securities into risk categories based on NAV erosion analysis.
    """
    
    RISK_CATEGORIES = {
        'minimal': {'max_prob_5pct': 20, 'max_median_erosion': 0, 'color': 'green'},
        'low': {'max_prob_5pct': 40, 'max_median_erosion': -2, 'color': 'yellow'},
        'moderate': {'max_prob_5pct': 60, 'max_median_erosion': -5, 'color': 'orange'},
        'high': {'max_prob_5pct': 80, 'max_median_erosion': -10, 'color': 'red'},
        'severe': {'max_prob_5pct': 100, 'max_median_erosion': -100, 'color': 'darkred'}
    }
    
    @classmethod
    def classify_risk(cls, erosion_analysis: Dict) -> str:
        """
        Classify NAV erosion risk level.
        
        Returns:
            Risk category: minimal, low, moderate, high, or severe
        """
        prob_5pct = erosion_analysis['probability_annual_erosion_gt_5pct']
        median_erosion = erosion_analysis['median_annualized_nav_change_pct']
        
        # Check categories from severe to minimal
        categories = ['severe', 'high', 'moderate', 'low', 'minimal']
        
        for category in categories:
            thresholds = cls.RISK_CATEGORIES[category]
            
            if (prob_5pct <= thresholds['max_prob_5pct'] and
                median_erosion >= thresholds['max_median_erosion']):
                return category
        
        return 'severe'  # Fallback
    
    @classmethod
    def get_risk_description(cls, risk_category: str) -> str:
        """Get human-readable risk description."""
        descriptions = {
            'minimal': 'Minimal NAV erosion risk. Strong capital preservation expected.',
            'low': 'Low NAV erosion risk. Minor erosion possible in adverse markets.',
            'moderate': 'Moderate NAV erosion risk. Significant erosion possible over time.',
            'high': 'High NAV erosion risk. Substantial capital erosion likely.',
            'severe': 'Severe NAV erosion risk. Major capital impairment probable.'
        }
        
        return descriptions.get(risk_category, 'Unknown risk level')
    
    @classmethod
    def should_flag_for_review(cls, risk_category: str) -> bool:
        """Determine if security should be flagged for manual review."""
        return risk_category in ['high', 'severe']


if __name__ == "__main__":
    # Example usage
    sample_analysis = {
        'median_annualized_nav_change_pct': -3.5,
        'probability_annual_erosion_gt_5pct': 55.0,
        'probability_annual_erosion_gt_10pct': 18.0,
        'probability_any_erosion': 72.0,
        'var_95_annualized_pct': -8.2,
        'var_99_annualized_pct': -12.5,
        'simulation_params': {
            'ticker': 'JEPI',
            'n_simulations': 10000,
            'years': 3
        }
    }
    
    integration = NAVErosionSustainabilityIntegration()
    penalty = integration.calculate_sustainability_penalty(sample_analysis, 'COVERED_CALL_ETF')
    
    print("Sustainability Penalty Calculation:")
    print(f"Penalty Points: {penalty['penalty_points']}")
    print(f"Severity: {penalty['severity']}")
    print(f"Rationale: {penalty['rationale']}")
    
    risk_category = NAVErosionRiskClassifier.classify_risk(sample_analysis)
    print(f"\nRisk Classification: {risk_category}")
    print(f"Description: {NAVErosionRiskClassifier.get_risk_description(risk_category)}")
    print(f"Flag for Review: {NAVErosionRiskClassifier.should_flag_for_review(risk_category)}")
