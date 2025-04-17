
import re
import logging
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Union
from lib.ai.llm_model import LlmModel

logger = logging.getLogger(__name__)

file_edit_prompt = """
We are currently editing a single file based on relevant part of following instructions:

--- BEGIN INSTRUCTIONS ---
{instructions}
--- END INSTRUCTIONS ---

Here is the file that we are editing based on the relevant part of the instructions:
--- BEGIN FILE ---
```
{content}
```
--- END FILE ---

Now determine if the file is indeed discussed and relevant to the instructions. If it is not relevant, immediately return

```
IRRELEVANT
```

and nothing else.

If it is relevant, continue and do the following:

Refocus on the part of the instructions that is directly relevant to the file be edited.

Now, make the edit based on the instructions by generating *SEARCH/REPLACE* edits.

Every *SEARCH/REPLACE* edit must use this format:
1. The start of search block: <<<<<<< SEARCH
2. A contiguous chunk of lines to search for in the existing source code
3. The dividing line: =======
4. The lines to replace into the source code
5. The end of the replace block: >>>>>>> REPLACE

Here is an example:

```edit
<<<<<<< SEARCH
from flask import Flask
=======
import math
from flask import Flask
>>>>>>> REPLACE
```

Please note that the *SEARCH/REPLACE* edit REQUIRES PROPER INDENTATION. If you would like to add the line '        print(x)', you must fully write that out, with all those spaces before the code!
Wrap the *SEARCH/REPLACE* edit in blocks ```edit...```
"""

file_update_prompt = """
We are currently updating a single file based on relevant part of following instructions:

--- BEGIN INSTRUCTIONS ---
{instructions}
--- END INSTRUCTIONS ---

Here is the file that we are updating based on the relevant part of the instructions:
--- BEGIN FILE ---
```
{content}
```
--- END FILE ---

Focus on the part of the instructions that is directly relevant to the file be updated.

Now, make the update based on the instructions by generating an ENTIRE_UPDATED_FILE block.

The *ENTIRE_UPDATED_FILE* must use this format:
1. The start of block: ======= ENTIRE_UPDATED_FILE
2. A contiguous chunk of lines of the fully updated file.
5. The end of the replace block: ======= ENTIRE_UPDATED_FILE

DO NOT change anything that wasn’t instructed. DO NOT make uninstructed changes or omissions. ONLY, dutifully make the updates as instructed.

Here is an example:

```edit
======= ENTIRE_UPDATED_FILE

<full updated text>

======= ENTIRE_UPDATED_FILE
```

Please note that the *ENTIRE_UPDATED_FILE* block REQUIRES PROPER INDENTATION. It should be exactly like the original file, but with the changes per the instructions only.
"""

file_create_prompt = """
We are currently determining which new files need to be created based on the following instructions:

--- BEGIN INSTRUCTIONS ---
{instructions}
--- END INSTRUCTIONS ---

List the relative file paths (from the repository root) of any files that should be created
because they are referenced or implied by these instructions but do not exist yet.
Return your answer wrapped in triple backticks, one path per line, for example:

```
src/new_module.py
tests/test_new_module.py
```

If no new files need to be created, return exactly:

```
No files to create.
```
"""

def parse_search_replace(response: str) -> Union[List[Dict[str, str]], str]:
    """
    Parses LLM response for all search/replace edit blocks.

    Returns:
        - list of dicts with 'search' and 'replace' keys if edits found
        - string 'irrelevant' if file deemed irrelevant
    """
    if "IRRELEVANT" in response:
        return "irrelevant"

    edits = []
    # Find all ```edit blocks
    for edit_block in re.findall(r"```(?:\s*)edit(.*?)(?=```)", response, re.DOTALL):
        # Find all <<<<<<< SEARCH ... ======= ... >>>>>>> REPLACE blocks inside
        pattern = r"<<<<<<<\s*SEARCH\s*\n(.*?)\n=======(.*?)>>>>>>> REPLACE"
        for match in re.finditer(pattern, edit_block, re.DOTALL):
            search = match.group(1)
            replace = match.group(2)
            # DO NOT strip leading spaces, preserve indentation
            # Remove possible trailing newlines only
            search = search.rstrip('\n')
            replace = replace.rstrip('\n')
            edits.append({'search': search, 'replace': replace})

    return edits


def parse_entire_file_update(response: str) -> Optional[str]:
    """
    Extracts the entire updated file content from LLM fallback response.

    Returns entire file string or None if not found.
    """
    pattern = r"={7}\s*ENTIRE_UPDATED_FILE\s*\n(.*?)\n={7}\s*ENTIRE_UPDATED_FILE"
    match = re.search(pattern, response, re.DOTALL)
    if match:
        return match.group(1).rstrip('\n')
    return None


def apply_edits(content: str, edits: List[Dict[str, str]]) -> Tuple[str, List[str], int]:
    """
    Attempts to apply each search/replace edit on the content exactly once.

    Returns:
        - updated content string
        - list of error messages (if any)
        - count of successful edits
    """
    updated = content
    errors = []
    success_count = 0

    for idx, edit in enumerate(edits, 1):
        search = edit['search']
        replace = edit['replace']

        # Exact substring match – safest for multi-line blocks
        pos = updated.find(search)
        if pos == -1:
            errors.append(f"Edit {idx}: search pattern not found.")
            logger.warning(f"[Edit {idx}] Search pattern not found.")
            continue

        updated = updated.replace(search, replace, 1)  # Replace first occurrence only
        logger.info(f"[Edit {idx}] Applied successfully.")
        success_count += 1

    return updated, errors, success_count


def edit_file(llm: LlmModel, content: str, instructions: str) -> Tuple[str, List[str]]:
    """
    Edits content using LLM-generated search/replace instructions, with fallback.

    Returns:
        - updated content string
        - list of error messages (empty if fully successful)
    """
    prompt = file_edit_prompt.format(instructions=instructions, content=content)
    logger.info("Sending edit prompt to LLM")
    response = llm.send_prompt(prompt)

    parse_result = parse_search_replace(response)

    if parse_result == "irrelevant":
        logger.info("File marked as irrelevant to instructions.")
        return content, ["File was deemed irrelevant to the instructions."]

    edits = parse_result
    updated_content, errors, success_count = apply_edits(content, edits)

    # Change this condition to check for any errors, not just zero successes
    if errors:  # Changed from: if success_count == 0
        logger.info("Some edits failed, attempting entire file fallback.")
        fallback_prompt = file_update_prompt.format(instructions=instructions, content=content)
        fallback_response = llm.send_prompt(fallback_prompt)
        updated_full = parse_entire_file_update(fallback_response)

        if updated_full is not None:
            logger.info("Fallback entire file update succeeded.")
            return updated_full, []
        else:
            logger.error("Fallback entire file update failed.")
            errors.append("Fallback update failed after partial edit application.")


    return updated_content, errors


async def edit_file_async(llm: LlmModel, content: str, instructions: str) -> Tuple[str, List[str]]:
    """
    Async version of edit_file.
    """
    prompt = file_edit_prompt.format(instructions=instructions, content=content)
    logger.info("Sending async edit prompt to LLM")
    response = await llm.send_prompt_async(prompt)

    parse_result = parse_search_replace(response)

    if parse_result == "irrelevant":
        logger.info("File marked as irrelevant to instructions.")
        return content, ["File was deemed irrelevant to the instructions."]

    edits = parse_result
    updated_content, errors, success_count = apply_edits(content, edits)

    # Change this condition to check for any errors, not just zero successes
    if errors:  # Changed from: if success_count == 0
        logger.info("Some edits failed, attempting entire file fallback (async).")
        fallback_prompt = file_update_prompt.format(instructions=instructions, content=content)
        fallback_response = await llm.send_prompt_async(fallback_prompt)
        updated_full = parse_entire_file_update(fallback_response)

        if updated_full is not None:
            logger.info("Fallback entire file update succeeded.")
            return updated_full, []
        else:
            logger.error("Fallback entire file update failed.")
            errors.append("Fallback update failed after partial edit application.")

    return updated_content, errors


def find_files_to_create(
    llm: LlmModel,
    instructions: str,
    root_dir: Union[str, Path] = "."
) -> Tuple[List[str], List[str]]:
    """
    Identify files that need to be created based on instructions.

    Args:
        llm: LLM model to query
        instructions: User instructions
        root_dir: Root directory for file paths

    Returns:
        Tuple of (files_to_create, errors)
    """
    # Prepare the prompt
    prompt = file_create_prompt.format(instructions=instructions)

    # Get response from LLM
    logger.info("Querying LLM for files to create")
    response = llm.send_prompt(prompt)
    logger.debug(f"LLM response for file creation:\n{response}")

    # Parse file paths from response
    suggested_paths = parse_file_create(response)

    # Check which files don't exist
    root = Path(root_dir)
    to_create = []
    errors = []

    for path in suggested_paths:
        full_path = root / path
        if not full_path.exists():
            to_create.append(path)
        else:
            msg = f"File '{path}' already exists"
            logger.info(msg)
            errors.append(msg)

    return to_create, errors


async def find_files_to_create_async(
    llm: LlmModel,
    instructions: str,
    root_dir: Union[str, Path] = "."
) -> Tuple[List[str], List[str]]:
    """
    Async version of find_files_to_create.
    """
    # Prepare the prompt
    prompt = file_create_prompt.format(instructions=instructions)

    # Get response from LLM
    logger.info("Querying LLM for files to create (async)")
    response = await llm.send_prompt_async(prompt)
    logger.debug(f"LLM response for file creation:\n{response}")

    # Parse file paths from response
    suggested_paths = parse_file_create(response)

    # Check which files don't exist
    root = Path(root_dir)
    to_create = []
    errors = []

    for path in suggested_paths:
        full_path = root / path
        if not full_path.exists():
            to_create.append(path)
        else:
            msg = f"File '{path}' already exists"
            logger.info(msg)
            errors.append(msg)

    return to_create, errors
