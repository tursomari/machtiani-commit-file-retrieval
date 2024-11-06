import asyncio
import logging
from fastapi import APIRouter, HTTPException
from app.utils import DataDir
from lib.utils.utilities import url_to_folder_name, get_lock_file_path
from lib.vcs.repo_manager import fetch_and_checkout_branch
from lib.utils.enums import FetchAndCheckoutBranchRequest
from app.models.requests import LoadRequest  # Import the LoadRequest model
from app.routes.load import handle_load
from app.models.responses import FetchAndCheckoutResponse  # Import the new response model

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/fetch-and-checkout", response_model=FetchAndCheckoutResponse)
@router.post("/fetch-and-checkout/", response_model=FetchAndCheckoutResponse)
async def handle_fetch_and_checkout_branch(data: FetchAndCheckoutBranchRequest):
    try:
        print(f"codehost_url: {data.codehost_url}")
        project_name = url_to_folder_name(str(data.codehost_url))  # Normalize the project name
        branch_name = data.branch_name
        lock_file_path = get_lock_file_path(project_name)

        # Call the repository manager to fetch and checkout the branch
        await asyncio.to_thread(
            fetch_and_checkout_branch,
            data.codehost_url,
            DataDir.REPO.get_path(project_name),
            project_name,
            branch_name,
            data.api_key
        )

        # Prepare the load request for counting tokens
        load_request = LoadRequest(  # Create an instance of LoadRequest
            openai_api_key=data.openai_api_key.get_secret_value() if data.openai_api_key else None,
            project_name=project_name,
            ignore_files=data.ignore_files
        )

        # Calling the load function to generate embeddings
        result_load = await handle_load(load_request)

        if result_load.get('status'):
            return FetchAndCheckoutResponse(
                message=f"Fetched and checked out branch '{data.branch_name}' for project '{data.project_name}' and updated index.",
                branch_name=data.branch_name,
                project_name=data.project_name,
            )
        else:
            logger.error(f"Load function returned an error: {result_load.get('error')}")
            raise HTTPException(status_code=400, detail="Error generating embeddings.")

    except HTTPException as e:
        logger.error(f"HTTP Exception: {e.detail}")
        raise e
    except Exception as e:
        logger.error("An error occurred while fetching and checking out the branch: %s", str(e))
        raise HTTPException(status_code=500, detail="Internal Server Error")
