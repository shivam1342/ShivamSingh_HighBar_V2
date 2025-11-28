"""
Main CLI entry point for Kasparro Agentic FB Analyst
Usage: python run.py "Analyze ROAS drop in last 7 days"
"""
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

from src.utils.config import load_config, setup_logging
from src.orchestrator import AgentOrchestrator

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)


def main():
    """Main execution function"""
    
    # Load configuration
    try:
        config = load_config("config/config.yaml")
        setup_logging(config)
    except Exception as e:
        print(f"ERROR: Failed to load configuration: {e}")
        sys.exit(1)
    
    # Get user query from command line
    if len(sys.argv) < 2:
        print("Usage: python run.py \"<your query>\"")
        print("Example: python run.py \"Analyze ROAS drop in last 7 days\"")
        sys.exit(1)
    
    user_query = sys.argv[1]
    
    # Initialize orchestrator
    try:
        logger.info("=" * 80)
        logger.info("Kasparro Agentic FB Analyst Starting")
        logger.info("=" * 80)
        
        orchestrator = AgentOrchestrator(config)
        
        # Run analysis
        results = orchestrator.run(user_query)
        
        # Save outputs
        orchestrator.save_outputs(results)
        
        logger.info("=" * 80)
        logger.info("Analysis Complete!")
        logger.info("=" * 80)
        logger.info(f"📊 Insights: {config['outputs']['insights_file']}")
        logger.info(f"🎨 Creatives: {config['outputs']['creatives_file']}")
        logger.info(f"📝 Report: {config['outputs']['report_file']}")
        logger.info(f"📋 Logs: {config['outputs']['logs_dir']}/execution.jsonl")
        
        print("\n✅ Analysis complete! Check the reports/ directory for outputs.")
        
    except FileNotFoundError as e:
        logger.error(f"Data file not found: {e}")
        print(f"\nERROR: {e}")
        print("Make sure synthetic_fb_ads_undergarments.csv is in the project root directory.")
        sys.exit(1)
        
    except Exception as e:
        logger.error(f"Execution failed: {e}", exc_info=True)
        print(f"\nERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
