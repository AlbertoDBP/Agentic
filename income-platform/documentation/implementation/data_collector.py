"""
NAV Erosion Data Collection Pipeline

Collects historical data and parameters needed for Monte Carlo NAV erosion
analysis, integrating with Agent 1 (Market Data) and database.
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
import json
from monte_carlo_engine import CoveredCallETFParams


class NAVErosionDataCollector:
    """
    Collects all data needed for NAV erosion Monte Carlo simulation.
    
    Integrates with:
    - Agent 1 (Market Data) for real-time/historical data
    - Database for covered call ETF metrics
    - External APIs as needed
    """
    
    def __init__(self, db_connection, market_data_agent=None):
        self.db = db_connection
        self.market_data = market_data_agent
        
        # Known covered call ETF configurations
        self.known_strategies = {
            'JEPI': {
                'call_moneyness_target': 0.02,
                'underlying_index': 'SPX',
                'strategy_description': 'S&P 500 with ~2% OTM calls'
            },
            'JEPQ': {
                'call_moneyness_target': 0.02,
                'underlying_index': 'NDX',
                'strategy_description': 'NASDAQ-100 with ~2% OTM calls'
            },
            'QYLD': {
                'call_moneyness_target': 0.00,
                'underlying_index': 'NDX',
                'strategy_description': 'NASDAQ-100 with ATM calls'
            },
            'XYLD': {
                'call_moneyness_target': 0.00,
                'underlying_index': 'SPX',
                'strategy_description': 'S&P 500 with ATM calls'
            },
            'RYLD': {
                'call_moneyness_target': 0.00,
                'underlying_index': 'RUT',
                'strategy_description': 'Russell 2000 with ATM calls'
            },
            'DIVO': {
                'call_moneyness_target': 0.03,
                'underlying_index': 'SPX',
                'strategy_description': 'Dividend stocks with ~3% OTM calls'
            },
            'SVOL': {
                'call_moneyness_target': 0.01,
                'underlying_index': 'SPX',
                'strategy_description': 'Low volatility with ~1% OTM calls'
            }
        }
    
    def collect_etf_parameters(
        self,
        ticker: str,
        lookback_months: int = 12
    ) -> CoveredCallETFParams:
        """
        Collect all parameters needed for NAV erosion simulation.
        
        Args:
            ticker: ETF ticker symbol
            lookback_months: Months of historical data to collect
        
        Returns:
            CoveredCallETFParams object ready for simulation
        
        Raises:
            ValueError: If insufficient data available
        """
        ticker = ticker.upper()
        
        # 1. Fetch current snapshot
        current_data = self._fetch_current_data(ticker)
        
        if not current_data:
            raise ValueError(f"No current data available for {ticker}")
        
        # 2. Fetch historical time series
        historical_data = self._fetch_historical_data(ticker, lookback_months)
        
        if not historical_data['premium_yields']:
            raise ValueError(f"No historical premium data available for {ticker}")
        
        # 3. Get strategy configuration
        strategy_config = self._get_strategy_config(ticker)
        
        # 4. Build params object
        params = CoveredCallETFParams(
            ticker=ticker,
            current_nav=current_data['nav'],
            current_price=current_data['price'],
            
            # Historical time series
            monthly_premium_yields=historical_data['premium_yields'],
            underlying_monthly_returns=historical_data['underlying_returns'],
            distribution_history=historical_data['distributions'],
            
            # Structural parameters
            expense_ratio_annual=current_data['expense_ratio'],
            leverage_ratio=current_data.get('leverage_ratio', 1.0),
            roc_percentage=current_data.get('roc_percentage', 0.0),
            
            # Options strategy parameters
            call_moneyness_target=strategy_config['call_moneyness_target'],
            call_coverage_ratio=current_data.get('coverage_ratio', 1.0),
            option_expiry_days=30  # Monthly standard
        )
        
        return params
    
    def _fetch_current_data(self, ticker: str) -> Optional[Dict]:
        """
        Fetch current snapshot from database.
        
        Returns most recent data point for the ticker.
        """
        query = """
            SELECT 
                nav,
                market_price as price,
                distribution_yield_ttm,
                expense_ratio,
                leverage_ratio,
                roc_percentage,
                data_date
            FROM covered_call_etf_metrics
            WHERE ticker = %s
            ORDER BY data_date DESC
            LIMIT 1
        """
        
        result = self.db.execute_one(query, [ticker])
        
        if not result:
            # Try to fetch from market data agent if available
            if self.market_data:
                return self._fetch_from_market_data(ticker)
            return None
        
        return dict(result)
    
    def _fetch_historical_data(self, ticker: str, months: int) -> Dict:
        """
        Fetch historical time series data.
        
        Returns:
            Dict with lists of premium_yields, underlying_returns, distributions
        """
        cutoff_date = datetime.now() - timedelta(days=months * 30)
        
        query = """
            SELECT 
                monthly_premium_yield,
                underlying_return_1m,
                monthly_distribution,
                data_date
            FROM covered_call_etf_metrics
            WHERE ticker = %s
                AND data_date >= %s
            ORDER BY data_date ASC
        """
        
        rows = self.db.execute_all(query, [ticker, cutoff_date])
        
        # Extract time series, filtering out None values
        premium_yields = [
            r['monthly_premium_yield'] 
            for r in rows 
            if r['monthly_premium_yield'] is not None
        ]
        
        underlying_returns = [
            r['underlying_return_1m']
            for r in rows
            if r['underlying_return_1m'] is not None
        ]
        
        distributions = [
            r['monthly_distribution']
            for r in rows
            if r['monthly_distribution'] is not None
        ]
        
        dates = [r['data_date'] for r in rows]
        
        return {
            'premium_yields': premium_yields,
            'underlying_returns': underlying_returns,
            'distributions': distributions,
            'dates': dates
        }
    
    def _get_strategy_config(self, ticker: str) -> Dict:
        """
        Get options strategy configuration for the ticker.
        
        Returns dict with call_moneyness_target and other strategy params.
        """
        # Check if we have known configuration
        if ticker in self.known_strategies:
            return self.known_strategies[ticker]
        
        # Try to infer from database metadata
        query = """
            SELECT 
                metadata
            FROM securities
            WHERE ticker = %s
        """
        
        result = self.db.execute_one(query, [ticker])
        
        if result and result['metadata']:
            metadata = result['metadata']
            
            # Try to extract strategy info from metadata
            strategy = metadata.get('strategy', '').lower()
            
            if 'at the money' in strategy or 'atm' in strategy:
                return {
                    'call_moneyness_target': 0.00,
                    'strategy_description': 'At-the-money covered calls'
                }
            elif 'out of the money' in strategy or 'otm' in strategy:
                # Try to extract percentage
                # Default to 2% OTM if not specified
                return {
                    'call_moneyness_target': 0.02,
                    'strategy_description': 'Out-of-the-money covered calls'
                }
        
        # Default conservative assumption
        return {
            'call_moneyness_target': 0.02,
            'strategy_description': 'Assumed ~2% OTM covered calls'
        }
    
    def _fetch_from_market_data(self, ticker: str) -> Optional[Dict]:
        """
        Fetch current data from market data agent (Agent 1).
        
        Fallback when database doesn't have recent data.
        """
        if not self.market_data:
            return None
        
        try:
            # This would integrate with actual Agent 1 interface
            # Placeholder for now
            data = self.market_data.get_quote(ticker)
            
            return {
                'nav': data.get('nav', data.get('price')),
                'price': data.get('price'),
                'expense_ratio': data.get('expense_ratio', 0.0035),
                'leverage_ratio': 1.0,
                'roc_percentage': 0.0
            }
        except Exception as e:
            print(f"Error fetching from market data: {e}")
            return None
    
    def validate_parameters(self, params: CoveredCallETFParams) -> Dict:
        """
        Validate collected parameters for completeness and reasonableness.
        
        Returns:
            Dict with validation results:
            - is_valid: bool
            - warnings: List[str]
            - errors: List[str]
        """
        warnings = []
        errors = []
        
        # Check data completeness
        if len(params.monthly_premium_yields) < 6:
            warnings.append(
                f"Limited premium history ({len(params.monthly_premium_yields)} months). "
                "Results may be less reliable."
            )
        
        if len(params.underlying_monthly_returns) < 6:
            warnings.append(
                f"Limited return history ({len(params.underlying_monthly_returns)} months). "
                "Results may be less reliable."
            )
        
        if not params.distribution_history or len(params.distribution_history) < 6:
            warnings.append(
                "Limited distribution history. Using default assumptions."
            )
        
        # Check data reasonableness
        if params.premium_yield_mean > 0.02:  # >2% monthly = >24% annual
            warnings.append(
                f"Very high average premium yield ({params.premium_yield_mean*12*100:.1f}% annualized). "
                "Verify data accuracy."
            )
        
        if params.underlying_annual_volatility > 0.50:  # >50% annual vol
            warnings.append(
                f"Extremely high volatility ({params.underlying_annual_volatility*100:.0f}%). "
                "Results may reflect unusual market conditions."
            )
        
        if params.expense_ratio_annual > 0.02:  # >2% expense ratio
            warnings.append(
                f"High expense ratio ({params.expense_ratio_annual*100:.2f}%). "
                "Will significantly impact NAV projections."
            )
        
        # Check for errors (deal-breakers)
        if params.current_nav <= 0:
            errors.append("Invalid NAV: must be positive")
        
        if params.expense_ratio_annual < 0 or params.expense_ratio_annual > 0.10:
            errors.append(
                f"Unreasonable expense ratio: {params.expense_ratio_annual*100:.2f}%"
            )
        
        if params.call_moneyness_target < -0.05 or params.call_moneyness_target > 0.10:
            errors.append(
                f"Unreasonable call moneyness: {params.call_moneyness_target*100:.1f}%"
            )
        
        return {
            'is_valid': len(errors) == 0,
            'warnings': warnings,
            'errors': errors,
            'completeness_score': self._calculate_completeness_score(params)
        }
    
    def _calculate_completeness_score(self, params: CoveredCallETFParams) -> float:
        """
        Calculate data completeness score (0-100).
        
        Higher is better. <70 means significant missing data.
        """
        score = 0.0
        
        # Premium data (30 points max)
        if len(params.monthly_premium_yields) >= 12:
            score += 30
        elif len(params.monthly_premium_yields) >= 6:
            score += 20
        elif len(params.monthly_premium_yields) >= 3:
            score += 10
        
        # Return data (30 points max)
        if len(params.underlying_monthly_returns) >= 12:
            score += 30
        elif len(params.underlying_monthly_returns) >= 6:
            score += 20
        elif len(params.underlying_monthly_returns) >= 3:
            score += 10
        
        # Distribution data (20 points max)
        if params.distribution_history and len(params.distribution_history) >= 12:
            score += 20
        elif params.distribution_history and len(params.distribution_history) >= 6:
            score += 15
        elif params.distribution_history and len(params.distribution_history) >= 3:
            score += 10
        
        # Structural parameters (20 points max)
        has_expense_ratio = params.expense_ratio_annual > 0
        has_roc_data = params.roc_percentage > 0
        has_strategy_config = params.call_moneyness_target is not None
        
        if has_expense_ratio:
            score += 10
        if has_roc_data or has_strategy_config:
            score += 10
        
        return round(score, 1)
    
    def store_collected_data(self, ticker: str, params: CoveredCallETFParams):
        """
        Store collected parameters for audit trail and future reference.
        """
        query = """
            INSERT INTO nav_erosion_data_collection_log
                (ticker, collection_date, params_json, completeness_score)
            VALUES (%s, CURRENT_TIMESTAMP, %s, %s)
        """
        
        params_dict = {
            'ticker': params.ticker,
            'current_nav': params.current_nav,
            'current_price': params.current_price,
            'data_points': {
                'premium_yields_count': len(params.monthly_premium_yields),
                'returns_count': len(params.underlying_monthly_returns),
                'distributions_count': len(params.distribution_history) if params.distribution_history else 0
            },
            'derived_params': {
                'underlying_annual_return_mean': params.underlying_annual_return_mean,
                'underlying_annual_volatility': params.underlying_annual_volatility,
                'premium_yield_mean': params.premium_yield_mean,
                'premium_yield_std': params.premium_yield_std,
                'premium_vol_correlation': params.premium_vol_correlation
            }
        }
        
        validation = self.validate_parameters(params)
        
        self.db.execute(
            query,
            [ticker, json.dumps(params_dict), validation['completeness_score']]
        )


class CoveredCallETFRegistry:
    """
    Registry of known covered call ETFs with metadata.
    
    Helps with automatic detection and parameter inference.
    """
    
    REGISTRY = {
        'JEPI': {
            'name': 'JPMorgan Equity Premium Income ETF',
            'inception_date': '2020-05-20',
            'underlying': 'S&P 500',
            'strategy': 'ELN with OTM calls',
            'typical_yield': 0.09
        },
        'JEPQ': {
            'name': 'JPMorgan NASDAQ Equity Premium Income ETF',
            'inception_date': '2022-05-03',
            'underlying': 'NASDAQ-100',
            'strategy': 'ELN with OTM calls',
            'typical_yield': 0.11
        },
        'QYLD': {
            'name': 'Global X NASDAQ 100 Covered Call ETF',
            'inception_date': '2013-12-11',
            'underlying': 'NASDAQ-100',
            'strategy': 'ATM covered calls',
            'typical_yield': 0.12
        },
        'XYLD': {
            'name': 'Global X S&P 500 Covered Call ETF',
            'inception_date': '2013-06-20',
            'underlying': 'S&P 500',
            'strategy': 'ATM covered calls',
            'typical_yield': 0.10
        },
        'RYLD': {
            'name': 'Global X Russell 2000 Covered Call ETF',
            'inception_date': '2019-07-30',
            'underlying': 'Russell 2000',
            'strategy': 'ATM covered calls',
            'typical_yield': 0.13
        },
        'DIVO': {
            'name': 'Amplify CWP Enhanced Dividend Income ETF',
            'inception_date': '2016-12-15',
            'underlying': 'Dividend stocks',
            'strategy': 'Conservative OTM calls',
            'typical_yield': 0.06
        },
        'SVOL': {
            'name': 'Simplify Volatility Premium ETF',
            'inception_date': '2020-05-20',
            'underlying': 'S&P 500 low vol',
            'strategy': 'VIX puts + OTM calls',
            'typical_yield': 0.12
        }
    }
    
    @classmethod
    def is_known_covered_call_etf(cls, ticker: str) -> bool:
        """Check if ticker is a known covered call ETF."""
        return ticker.upper() in cls.REGISTRY
    
    @classmethod
    def get_metadata(cls, ticker: str) -> Optional[Dict]:
        """Get metadata for a known covered call ETF."""
        return cls.REGISTRY.get(ticker.upper())
    
    @classmethod
    def get_all_tickers(cls) -> List[str]:
        """Get list of all known covered call ETF tickers."""
        return list(cls.REGISTRY.keys())


if __name__ == "__main__":
    # Example usage (would need actual DB connection)
    print("NAV Erosion Data Collector")
    print("\nKnown Covered Call ETFs:")
    for ticker in CoveredCallETFRegistry.get_all_tickers():
        metadata = CoveredCallETFRegistry.get_metadata(ticker)
        print(f"  {ticker}: {metadata['name']}")
        print(f"    Strategy: {metadata['strategy']}")
        print(f"    Typical Yield: {metadata['typical_yield']*100:.1f}%")
