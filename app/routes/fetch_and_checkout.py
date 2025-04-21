import asyncio
import logging
from fastapi import APIRouter, HTTPException
from app.utils import DataDir
from lib.utils.utilities import url_to_folder_name, get_lock_file_path

from lib.vcs.repo_manager import fetch_and_checkout_branch, fetch_and_checkout_commit
from app.models.requests import LoadRequest, FetchAndCheckoutBranchRequest  # Import the LoadRequest model
from app.routes.load import handle_load
from app.models.responses import FetchAndCheckoutResponse  # Import the new response model

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/fetch-and-checkout", response_model=FetchAndCheckoutResponse)
@router.post("/fetch-and-checkout/", response_model=FetchAndCheckoutResponse)
async def handle_fetch_and_checkout_branch(data: FetchAndCheckoutBranchRequest):
    try:
        logger.info(f"Received request to fetch and checkout for project '{data.project_name}'.")

        project_name = url_to_folder_name(str(data.codehost_url))
        lock_file_path = get_lock_file_path(project_name)

        if data.branch_name:
            # If branch name is provided, use the branch checkout function
            logger.info(f"Fetching and checking out branch '{data.branch_name}'")
            await asyncio.to_thread(
                fetch_and_checkout_branch,
                data.codehost_url,
                DataDir.REPO.get_path(project_name),
                project_name,
                data.branch_name,
                data.api_key
            )
        else:
            # Otherwise, use the commit checkout function
            logger.info(f"Fetching and checking out commit '{data.commit_oid}'")
            await asyncio.to_thread(
                fetch_and_checkout_commit,
                data.codehost_url,
                DataDir.REPO.get_path(project_name),
                project_name,
                data.commit_oid,
                data.api_key
            )


        logger.info(f"Calling load with use_mock_llm: {data.use_mock_llm}")
        load_request = LoadRequest(
            embeddings_model=None,
            llm_model=None,
            embeddings_model_api_key=data.llm_model_api_key.get_secret_value() if data.llm_model_api_key else None,
            llm_model_api_key=data.llm_model_api_key.get_secret_value() if data.llm_model_api_key else None,
            llm_model_base_url=data.llm_model_base_url,
            project_name=project_name,
            ignore_files=data.ignore_files,
            head=data.head,
            use_mock_llm=data.use_mock_llm or False,
            amplification_level=data.amplification_level,
            depth_level=data.depth_level
        )

        result_load = await handle_load(load_request)

        if result_load.get('status'):

            return FetchAndCheckoutResponse(
                message=f"Fetched and checked out {'branch ' + data.branch_name if data.branch_name else 'commit ' + data.commit_oid} for project '{data.project_name}' and updated index.",
                branch_name=data.branch_name,
                commit_oid=data.commit_oid,
                project_name=data.project_name,
            )
        else:
            logger.error(f"Load function returned an error: {result_load.get('error')}")
            raise HTTPException(status_code=400, detail="Error generating embeddings.")

    except HTTPException as e:
        logger.error(f"HTTP Exception: {e.detail}")
        raise e
    except ValueError as e:
        logger.error(f"Value Error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:

        logger.error("An unexpected error occurred while fetching and checking out: %s", str(e))
        raise HTTPException(status_code=500, detail="Internal Server Error")
