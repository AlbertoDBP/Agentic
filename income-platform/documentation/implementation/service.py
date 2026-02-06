"""
NAV Erosion Analysis Microservice

FastAPI service providing Monte Carlo NAV erosion analysis endpoints
for the Income Fortress Platform.
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict
from datetime import datetime
import uvicorn
import logging

from monte_carlo_engine import (
    CoveredCallETFParams,
    EnhancedMonteCarloNAVErosion,
    OptimizedMonteCarloEngine,
    quick_nav_erosion_analysis,
    deep_nav_erosion_analysis
)
from sustainability_integration import (
    NAVErosionSustainabilityIntegration,
    NAVErosionRiskClassifier
)
from data_collector import NAVErosionDataCollector, CoveredCallETFRegistry

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="NAV Erosion Analysis Service",
    description="Monte Carlo simulation for covered call ETF NAV erosion analysis",
    version="1.0.0"
)

# Dependency injection for database
def get_db():
    """Get database connection (placeholder - implement based on your DB setup)."""
    # This would return actual DB connection
    # For now, returning None - actual implementation needed
    return None


# Request/Response Models
class NAVErosionRequest(BaseModel):
    """Request model for NAV erosion analysis."""
    ticker: str = Field(..., description="ETF ticker symbol", min_length=1, max_length=10)
    analysis_type: str = Field(
        default="quick",
        description="Analysis type: 'quick' (10K sims) or 'deep' (50K sims)"
    )
    years: int = Field(default=3, ge=1, le=10, description="Simulation horizon in years")
    force_refresh: bool = Field(
        default=False,
        description="Force new analysis even if cached result exists"
    )
    
    @validator('analysis_type')
    def validate_analysis_type(cls, v):
        if v not in ['quick', 'deep']:
            raise ValueError("analysis_type must be 'quick' or 'deep'")
        return v
    
    @validator('ticker')
    def validate_ticker(cls, v):
        return v.upper().strip()


class NAVErosionResponse(BaseModel):
    """Response model for NAV erosion analysis."""
    ticker: str
    analysis_type: str
    cached: bool
    results: Dict
    sustainability_impact: Dict
    risk_classification: Dict
    data_quality: Optional[Dict] = None
    generated_at: str
    cache_expires_at: Optional[str] = None


class BatchAnalysisRequest(BaseModel):
    """Request model for batch analysis."""
    tickers: List[str] = Field(..., max_items=50, description="List of tickers to analyze")
    analysis_type: str = Field(default="quick")
    force_refresh: bool = Field(default=False)
    
    @validator('analysis_type')
    def validate_analysis_type(cls, v):
        if v not in ['quick', 'deep']:
            raise ValueError("analysis_type must be 'quick' or 'deep'")
        return v


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    service: str
    timestamp: str
    version: str


# Initialize components (with None db for now - would be actual connection)
integration = NAVErosionSustainabilityIntegration(db_connection=None)
collector = NAVErosionDataCollector(db_connection=None, market_data_agent=None)


# Endpoints
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.
    
    Returns service status and metadata.
    """
    return HealthResponse(
        status="healthy",
        service="nav-erosion-analysis",
        timestamp=datetime.utcnow().isoformat(),
        version="1.0.0"
    )


@app.post("/analyze", response_model=NAVErosionResponse)
async def analyze_nav_erosion(
    request: NAVErosionRequest,
    background_tasks: BackgroundTasks,
    db=Depends(get_db)
):
    """
    Run NAV erosion analysis for a single ticker.
    
    Returns comprehensive Monte Carlo simulation results with:
    - NAV erosion probabilities
    - Sustainability score impact
    - Risk classification
    - Distribution projections
    
    Results are cached for 30 days unless force_refresh=True.
    """
    ticker = request.ticker
    
    logger.info(f"NAV erosion analysis request for {ticker} ({request.analysis_type})")
    
    try:
        # Check cache unless force refresh
        cached_result = None
        if not request.force_refresh:
            cached_result = integration.get_cached_analysis(
                ticker, 
                request.analysis_type,
                max_age_days=30
            )
        
        if cached_result:
            logger.info(f"Returning cached result for {ticker} (age: {cached_result['cache_age_days']} days)")
            
            # Calculate risk classification from cached results
            risk_category = NAVErosionRiskClassifier.classify_risk(cached_result['results'])
            
            return NAVErosionResponse(
                ticker=ticker,
                analysis_type=request.analysis_type,
                cached=True,
                results=cached_result['results'],
                sustainability_impact={'penalty_points': cached_result['penalty']},
                risk_classification={
                    'category': risk_category,
                    'description': NAVErosionRiskClassifier.get_risk_description(risk_category),
                    'flag_for_review': NAVErosionRiskClassifier.should_flag_for_review(risk_category)
                },
                generated_at=cached_result['analysis_date'],
                cache_expires_at=(
                    datetime.fromisoformat(cached_result['analysis_date']) + 
                    timedelta(days=30)
                ).isoformat()
            )
        
        # Collect parameters
        try:
            params = collector.collect_etf_parameters(ticker, lookback_months=12)
        except Exception as e:
            logger.error(f"Failed to collect parameters for {ticker}: {str(e)}")
            raise HTTPException(
                status_code=404,
                detail=f"Unable to collect data for {ticker}: {str(e)}"
            )
        
        # Validate parameters
        validation = collector.validate_parameters(params)
        
        if not validation['is_valid']:
            logger.warning(f"Parameter validation failed for {ticker}: {validation['errors']}")
            raise HTTPException(
                status_code=422,
                detail={
                    'message': 'Parameter validation failed',
                    'errors': validation['errors'],
                    'warnings': validation['warnings']
                }
            )
        
        # Log warnings if any
        if validation['warnings']:
            logger.warning(f"Parameter warnings for {ticker}: {validation['warnings']}")
        
        # Run simulation
        logger.info(f"Running {request.analysis_type} simulation for {ticker} ({request.years} years)")
        
        if request.analysis_type == 'quick':
            engine = OptimizedMonteCarloEngine(params)
            results = engine.simulate_vectorized(years=request.years, n_simulations=10000)
        else:  # deep
            engine = OptimizedMonteCarloEngine(params)
            results = engine.simulate_vectorized(years=request.years, n_simulations=50000)
        
        logger.info(f"Simulation complete for {ticker}")
        
        # Calculate sustainability impact
        penalty_result = integration.calculate_sustainability_penalty(
            results,
            asset_class='COVERED_CALL_ETF'
        )
        
        # Classify risk
        risk_category = NAVErosionRiskClassifier.classify_risk(results)
        
        # Cache results in background
        if db:  # Only cache if we have DB connection
            background_tasks.add_task(
                integration.cache_analysis,
                ticker,
                request.analysis_type,
                results,
                penalty_result['penalty_points'],
                valid_days=30
            )
        
        return NAVErosionResponse(
            ticker=ticker,
            analysis_type=request.analysis_type,
            cached=False,
            results=results,
            sustainability_impact=penalty_result,
            risk_classification={
                'category': risk_category,
                'description': NAVErosionRiskClassifier.get_risk_description(risk_category),
                'flag_for_review': NAVErosionRiskClassifier.should_flag_for_review(risk_category)
            },
            data_quality={
                'completeness_score': validation['completeness_score'],
                'warnings': validation['warnings']
            },
            generated_at=datetime.utcnow().isoformat(),
            cache_expires_at=(datetime.utcnow() + timedelta(days=30)).isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error analyzing {ticker}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@app.post("/batch-analyze")
async def batch_analyze(
    request: BatchAnalysisRequest,
    background_tasks: BackgroundTasks,
    db=Depends(get_db)
):
    """
    Batch analysis for multiple tickers.
    
    Useful for daily scoring runs across multiple covered call ETFs.
    Maximum 50 tickers per request.
    """
    logger.info(f"Batch analysis request for {len(request.tickers)} tickers")
    
    results = {}
    
    for ticker in request.tickers:
        try:
            single_request = NAVErosionRequest(
                ticker=ticker,
                analysis_type=request.analysis_type,
                force_refresh=request.force_refresh
            )
            
            result = await analyze_nav_erosion(single_request, background_tasks, db)
            results[ticker] = result.dict()
            
        except HTTPException as e:
            results[ticker] = {
                'error': e.detail,
                'status_code': e.status_code
            }
        except Exception as e:
            logger.error(f"Error in batch analysis for {ticker}: {str(e)}")
            results[ticker] = {
                'error': str(e),
                'status_code': 500
            }
    
    # Summary statistics
    successful = sum(1 for r in results.values() if 'error' not in r)
    failed = len(results) - successful
    
    return {
        'batch_summary': {
            'total_tickers': len(request.tickers),
            'successful': successful,
            'failed': failed,
            'analysis_type': request.analysis_type
        },
        'results': results,
        'generated_at': datetime.utcnow().isoformat()
    }


@app.get("/registry/covered-call-etfs")
async def get_covered_call_etf_registry():
    """
    Get registry of known covered call ETFs.
    
    Returns metadata for all ETFs in the system's registry.
    """
    return {
        'etfs': {
            ticker: CoveredCallETFRegistry.get_metadata(ticker)
            for ticker in CoveredCallETFRegistry.get_all_tickers()
        },
        'count': len(CoveredCallETFRegistry.get_all_tickers())
    }


@app.get("/ticker/{ticker}/should-analyze")
async def should_analyze_ticker(ticker: str):
    """
    Check if a ticker should have NAV erosion analysis run.
    
    Returns recommendation based on asset class and known strategies.
    """
    ticker = ticker.upper()
    
    # Check if it's a known covered call ETF
    is_known = CoveredCallETFRegistry.is_known_covered_call_etf(ticker)
    
    # Would also check asset class from database if available
    should_analyze = is_known  # Simplified logic
    
    return {
        'ticker': ticker,
        'should_analyze': should_analyze,
        'is_known_covered_call_etf': is_known,
        'metadata': CoveredCallETFRegistry.get_metadata(ticker) if is_known else None
    }


@app.delete("/cache/{ticker}")
async def invalidate_cache(ticker: str, db=Depends(get_db)):
    """
    Invalidate cached analysis for a ticker.
    
    Use when underlying data changes significantly or to force fresh analysis.
    """
    ticker = ticker.upper()
    
    if db:
        integration.invalidate_cache(ticker)
        return {
            'ticker': ticker,
            'cache_invalidated': True,
            'timestamp': datetime.utcnow().isoformat()
        }
    else:
        return {
            'ticker': ticker,
            'cache_invalidated': False,
            'message': 'No database connection'
        }


@app.get("/statistics/penalties")
async def get_penalty_statistics(asset_class: Optional[str] = None, db=Depends(get_db)):
    """
    Get summary statistics of NAV erosion penalties.
    
    Useful for monitoring and calibration.
    """
    if not db:
        return {
            'error': 'Database connection required',
            'statistics': None
        }
    
    stats = integration.get_penalty_summary_statistics(asset_class)
    
    return {
        'asset_class_filter': asset_class,
        'statistics': stats,
        'generated_at': datetime.utcnow().isoformat()
    }


# Error handlers
@app.exception_handler(ValueError)
async def value_error_handler(request, exc):
    return JSONResponse(
        status_code=400,
        content={'detail': str(exc)}
    )


# Startup/shutdown events
@app.on_event("startup")
async def startup_event():
    logger.info("NAV Erosion Analysis Service starting up")
    logger.info(f"Known covered call ETFs: {len(CoveredCallETFRegistry.get_all_tickers())}")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("NAV Erosion Analysis Service shutting down")


if __name__ == "__main__":
    # Run with: python service.py
    # Or with uvicorn: uvicorn service:app --host 0.0.0.0 --port 8003
    uvicorn.run(
        "service:app",
        host="0.0.0.0",
        port=8003,
        reload=True,
        log_level="info"
    )
