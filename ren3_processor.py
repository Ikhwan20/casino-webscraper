#!/usr/bin/env python3
"""
Ren3 Agent Processor
Automates batch processing of casino promotion JSONs through Ren3 AI Agent
"""

import os
import sys
import json
import time
import uuid
import logging
import requests
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)-8s %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('ren3_processor.log')
    ]
)
logger = logging.getLogger(__name__)


class Ren3Config:
    """Configuration for Ren3 API"""
    def __init__(self):
        self.api_url = os.getenv('REN3_API_URL', 'https://backend.ren3.ai')
        self.user_id = os.getenv('REN3_USER_ID')
        self.workspace_id = os.getenv('REN3_WORKSPACE_ID')
        self.agent_uuid = os.getenv('REN3_AGENT_UUID')
        self.agent_folder = os.getenv('REN3_AGENT_FOLDER')
        self.batch_size = int(os.getenv('BATCH_SIZE', '30'))
        self.poll_interval = int(os.getenv('POLL_INTERVAL', '15'))
        self.max_retries = int(os.getenv('MAX_RETRIES', '3'))
        
        # Validate required config
        required = ['user_id', 'workspace_id', 'agent_uuid', 'agent_folder']
        missing = [k for k in required if not getattr(self, k)]
        if missing:
            raise ValueError(f"Missing required config: {', '.join(missing)}")


class Ren3AgentProcessor:
    """Handles batch processing of JSONs through Ren3 AI Agent"""
    
    def __init__(self, config: Ren3Config):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'Ren3-Processor/1.0'
        })
    
    def _api_call(self, endpoint: str, data: dict, files: dict = None, 
                  method: str = 'POST') -> dict:
        """Make API call with retry logic"""
        url = f"{self.config.api_url}{endpoint}"
        
        for attempt in range(self.config.max_retries):
            try:
                if files:
                    # For file uploads, don't send JSON
                    response = self.session.post(url, data=data, files=files, timeout=300)
                else:
                    if method == 'POST':
                        response = self.session.post(url, json=data, timeout=60)
                    else:
                        response = self.session.get(url, params=data, timeout=60)
                
                response.raise_for_status()
                return response.json()
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"API call failed (attempt {attempt + 1}/{self.config.max_retries}): {e}")
                if attempt < self.config.max_retries - 1:
                    time.sleep(5 * (attempt + 1))  # Exponential backoff
                else:
                    raise
    
    def get_json_files(self, promo_folder: Path) -> List[Path]:
        """Get all JSON files except special files"""
        json_files = []
        for file in promo_folder.glob("*.json"):
            # Skip special files
            if file.name.startswith('_'):
                continue
            json_files.append(file)
        
        # Sort by filename for consistent ordering
        json_files.sort()
        logger.info(f"Found {len(json_files)} JSON files to process")
        return json_files
    
    def create_batches(self, json_files: List[Path]) -> List[List[Path]]:
        """Split JSON files into batches"""
        batches = []
        for i in range(0, len(json_files), self.config.batch_size):
            batch = json_files[i:i + self.config.batch_size]
            batches.append(batch)
        
        logger.info(f"Created {len(batches)} batches of up to {self.config.batch_size} files")
        return batches
    
    def upload_files(self, batch: List[Path], temp_folder_uuid: str) -> dict:
        """Upload batch of JSON files to Ren3"""
        logger.info(f"Uploading {len(batch)} files...")
        
        # Prepare multipart form data
        files = []
        form_data = {
            'workspaceid': self.config.workspace_id,
            'useruuid': self.config.user_id,
            'uploadtype': 'agents',
            'fileignoreparent': 'false',
            'parentfolder': temp_folder_uuid,
            'forceOverwrite': 'true',
            'tempfolderuuid': temp_folder_uuid,
            'agentuuid': self.config.agent_uuid,
            'agent_folder': self.config.agent_folder,
            'extra': json.dumps({
                'tempfolderuuid': temp_folder_uuid,
                'agentuuid': self.config.agent_uuid,
                'agent_folder': self.config.agent_folder
            })
        }
        
        # Add all files
        for json_file in batch:
            files.append(('file', (json_file.name, open(json_file, 'rb'), 'application/json')))
        
        try:
            response = self._api_call('/upload_agenttmpfiles', data=form_data, files=files)
            
            # Close all file handles
            for _, (_, file_obj, _) in files:
                file_obj.close()
            
            if response.get('success'):
                logger.info(f"Uploaded {len(batch)} files successfully")
                return response
            else:
                raise Exception(f"Upload failed: {response}")
                
        except Exception as e:
            # Close file handles on error
            for _, (_, file_obj, _) in files:
                try:
                    file_obj.close()
                except:
                    pass
            raise
    
    def get_job_input_files(self, temp_folder_uuid: str) -> List[Dict]:
        """Get list of uploaded files from temp folder"""
        logger.info("Verifying uploaded files...")
        
        data = {
            'input_folder': temp_folder_uuid,
            'userid': self.config.user_id,
            'workspaceid': self.config.workspace_id
        }
        
        response = self._api_call('/agentdrive/get_jobinputfiles', data)
        
        if response.get('success'):
            files = response.get('returnObject', [])
            logger.info(f"Verified {len(files)} files in temp folder")
            return files
        else:
            raise Exception(f"Failed to get input files: {response}")
    
    def run_agent(self, input_files: List[Dict], temp_folder_uuid: str) -> str:
        """Run the Ren3 agent on uploaded files"""
        logger.info(f"Running agent on {len(input_files)} files...")
        
        data = {
            'data': {
                'agent_uuid': self.config.agent_uuid,
                'input_files': input_files,
                'temp_folder': temp_folder_uuid
            },
            'userid': self.config.user_id,
            'workspaceid': self.config.workspace_id
        }
        
        response = self._api_call('/agentdrive/run_agent', data)
        
        if response.get('success'):
            job_id = response['returnObject']['uuid']
            logger.info(f"Agent started - Job ID: {job_id}")
            return job_id
        else:
            raise Exception(f"Failed to run agent: {response}")
    
    def poll_job_status(self, job_id: str) -> bool:
        """Poll job status until completion"""
        logger.info("Waiting for agent to complete...")
        
        start_time = time.time()
        last_progress = None
        
        while True:
            data = {
                'uuid': job_id,
                'userid': self.config.user_id,
                'workspaceid': self.config.workspace_id
            }
            
            try:
                response = self._api_call('/agentdrive/get_agentjoblogs', data)
                
                if response.get('success'):
                    logs = response.get('returnObject', [])
                    
                    # Check for completion
                    for log in logs:
                        if log.get('type') == 2:
                            text = log.get('text', '')
                            if 'completed' in text.lower():
                                elapsed = time.time() - start_time
                                logger.info(f"✓ Agent completed in {elapsed:.0f} seconds")
                                return True
                        
                        # Show progress updates
                        if 'progress' in log.get('text', '').lower():
                            progress = log.get('text')
                            if progress != last_progress:
                                logger.info(f"  Progress: {progress}")
                                last_progress = progress
                
                # Wait before next poll
                time.sleep(self.config.poll_interval)
                
            except Exception as e:
                logger.warning(f"Error polling status: {e}")
                time.sleep(self.config.poll_interval)
    
    def get_job_details(self, job_id: str) -> dict:
        """Get job details including output folder"""
        logger.info("Getting job details...")
        
        data = {
            'detailed': 1,
            'uuid': job_id,
            'userid': self.config.user_id,
            'workspaceid': self.config.workspace_id
        }
        
        response = self._api_call('/agentdrive/get_jobdetails', data)
        
        if response.get('success'):
            job_details = response['returnObject']
            output_folder = job_details['agentJob']['output_folder']
            logger.info(f"✓ Output folder: {output_folder}")
            return job_details
        else:
            raise Exception(f"Failed to get job details: {response}")
    
    def get_output_files(self, output_folder: str) -> List[Dict]:
        """Get list of output files from output folder"""
        logger.info("Fetching output files...")
        
        data = {
            'type': 'agents',
            'fields': ['uuid', 'doc_filename', 'is_folder', 'doc_extension'],
            'filter': {
                'status': ['', None],
                'parent_folder': output_folder,
                'workspace_id': self.config.workspace_id,
                'ingestion_status': 5,
                'folder_type': {'operator': 'ISNULLANDVALUE', 'value': 0},
                'isbundlechild': {'operator': 'ISNULLANDVALUE', 'value': 0},
                'latest_version': 1
            },
            'parent_folder': output_folder,
            'useruuid': self.config.user_id,
            'workspaceid': self.config.workspace_id,
            'order': 'is_folder DESC,folder_type ASC,doc_filename ASC'
        }
        
        response = self._api_call('/tensordrive/get_docs', data)
        
        if response.get('success'):
            files = response.get('returnObject', [])
            logger.info(f"✓ Found {len(files)} output files")
            return files
        else:
            raise Exception(f"Failed to get output files: {response}")
    
    def download_csv(self, doc_uuid: str, output_path: Path) -> Path:
        """Download CSV file from Ren3"""
        logger.info(f"Downloading CSV to {output_path.name}...")
        
        data = {
            'docuuid': doc_uuid,
            'userid': self.config.user_id,
            'workspaceid': self.config.workspace_id
        }
        
        url = f"{self.config.api_url}/tensordrive/get_filestream"
        
        try:
            response = self.session.post(url, json=data, timeout=120, stream=True)
            response.raise_for_status()
            
            # Save file
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            logger.info(f"Downloaded {output_path.name}")
            return output_path
            
        except Exception as e:
            logger.error(f"Failed to download CSV: {e}")
            raise
    
    def combine_csvs(self, csv_files: List[Path], output_path: Path) -> Path:
        """Combine multiple CSV files into one Excel file"""
        logger.info(f"Combining {len(csv_files)} CSV files...")
        
        combined_df = pd.DataFrame()
        
        for csv_file in csv_files:
            try:
                df = pd.read_csv(csv_file)
                combined_df = pd.concat([combined_df, df], ignore_index=True)
                logger.info(f"  Added {len(df)} rows from {csv_file.name}")
            except Exception as e:
                logger.error(f"  Failed to read {csv_file.name}: {e}")
        
        # Save as Excel
        combined_df.to_excel(output_path, index=False, engine='openpyxl')
        logger.info(f"✓ Combined Excel saved: {output_path}")
        logger.info(f"  Total rows: {len(combined_df)}")
        
        return output_path
    
    def process_promo_folder(self, promo_folder_path: str) -> Optional[Path]:
        """Main processing pipeline"""
        promo_folder = Path(promo_folder_path)
        
        if not promo_folder.exists():
            logger.error(f"Folder not found: {promo_folder}")
            return None
        
        logger.info("=" * 60)
        logger.info("REN3 AGENT PROCESSOR")
        logger.info("=" * 60)
        logger.info(f"Processing: {promo_folder.name}")
        logger.info(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Create output directory
        processed_dir = Path('processed') / promo_folder.name
        processed_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Get all JSON files
            json_files = self.get_json_files(promo_folder)
            
            if not json_files:
                logger.warning("No JSON files found to process")
                return None
            
            # Create batches
            batches = self.create_batches(json_files)
            
            # Process each batch
            csv_files = []
            
            for batch_num, batch in enumerate(batches, 1):
                logger.info(f"\n{'=' * 60}")
                logger.info(f"BATCH {batch_num}/{len(batches)}")
                logger.info(f"{'=' * 60}")
                
                try:
                    # Generate temp folder UUID
                    temp_folder_uuid = str(uuid.uuid4())
                    logger.info(f"Temp folder: {temp_folder_uuid}")
                    
                    # Upload files
                    upload_response = self.upload_files(batch, temp_folder_uuid)
                    
                    # Wait a bit for ingestion
                    logger.info("Waiting for file ingestion...")
                    time.sleep(5)
                    
                    # Verify upload
                    input_files = self.get_job_input_files(temp_folder_uuid)
                    
                    # Run agent
                    job_id = self.run_agent(input_files, temp_folder_uuid)
                    
                    # Poll for completion
                    self.poll_job_status(job_id)
                    
                    # Get output folder
                    job_details = self.get_job_details(job_id)
                    output_folder = job_details['agentJob']['output_folder']
                    
                    # Get output files
                    output_files = self.get_output_files(output_folder)
                    
                    # Find the CSV file
                    csv_file = None
                    for file in output_files:
                        if file['doc_filename'] == 'competitive_analysis_results.csv':
                            csv_file = file
                            break
                    
                    if not csv_file:
                        logger.warning(f"CSV file not found in output for batch {batch_num}")
                        continue
                    
                    # Download CSV
                    csv_path = processed_dir / f"batch_{batch_num:03d}.csv"
                    self.download_csv(csv_file['uuid'], csv_path)
                    csv_files.append(csv_path)
                    
                    logger.info(f"✓ Batch {batch_num} completed successfully")
                    
                except Exception as e:
                    logger.error(f"✗ Batch {batch_num} failed: {e}")
                    continue
                
                # Small delay between batches
                if batch_num < len(batches):
                    logger.info("Waiting 5 seconds before next batch...")
                    time.sleep(5)
            
            # Combine all CSVs
            if csv_files:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                final_excel = processed_dir / f"final_analysis_{timestamp}.xlsx"
                self.combine_csvs(csv_files, final_excel)
                
                logger.info(f"\n{'=' * 60}")
                logger.info("PROCESSING COMPLETE!")
                logger.info(f"{'=' * 60}")
                logger.info(f"Processed: {len(csv_files)} batches")
                logger.info(f"Output: {final_excel}")
                logger.info(f"Location: {final_excel.absolute()}")
                
                return final_excel
            else:
                logger.error("No batches were processed successfully")
                return None
                
        except Exception as e:
            logger.error(f"Processing failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python ren3_processor.py <promo_folder_path>")
        print("Example: python ren3_processor.py output/promo_20251020_080000")
        sys.exit(1)
    
    promo_folder = sys.argv[1]
    
    try:
        # Load configuration
        config = Ren3Config()
        
        # Create processor
        processor = Ren3AgentProcessor(config)
        
        # Process folder
        result = processor.process_promo_folder(promo_folder)
        
        if result:
            print(f"\nSUCCESS! Final output: {result}")
            sys.exit(0)
        else:
            print(f"\nFAILED! Check logs for details")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()