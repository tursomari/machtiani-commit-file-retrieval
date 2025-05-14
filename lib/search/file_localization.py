#!/usr/bin/env python3
import os
import json
import logging
from pathlib import Path
from lib.ai.llm_model import LlmModel # Assuming LlmModel is correctly importable

# Set up logging
logger = logging.getLogger(__name__)

class FileLocalizer:
    """
    A standalone file localizer that identifies relevant files based on a problem statement.
    """

    obtain_relevant_files_prompt = """
Please look through the following GitHub problem description and Repository structure and provide a list of files that may be relevant.

### GitHub Problem Description ###
{problem_statement}
###

### Repository Structure ###
{structure}
###

Please only provide the full paths relative to the repository root directory and return at most 5 files.
The returned files should be separated by new lines, listed in order of relevancy (most relevant at the top), and wrapped with triple backticks ```.
For example:
```
file1.py
folder/file2.py
another_folder/file3.py
```

If no files seem relevant, return:
```
No relevant files found.
```

Please make sure all the possibly relevant file paths are relative to the root directory of the provided repository structure.
"""

    refine_relevant_files_prompt = """
Let's refine our file selection. I've identified some potentially relevant files and obtained their summaries:

### Initial Relevant Files with Summaries ###
{file_summaries}
###

Given these summaries and the original problem, please identify any ADDITIONAL files that may be relevant.

### GitHub Problem Description ###
{problem_statement}
###

### Repository Structure ###
{structure}
###

Please only provide the full paths of ADDITIONAL files (not already mentioned above) that may be relevant.
The returned files should be separated by new lines, listed in order of relevancy (most relevant at the top), and wrapped with triple backticks ```.
For example:
```
additional_file1.py
folder/additional_file2.py
```

If no additional files seem relevant, return:
```
No additional relevant files.
```

Please make sure all the possibly relevant file paths are relative to the root directory of the provided repository structure.
"""

    def __init__(
        self,
        problem_statement: str,
        root_dir: str = ".",
        # --- Arguments needed for LlmModel ---
        api_key: str | None = None,
        model: str | None = None, # Allow LlmModel to use its default if None
        base_url: str | None = None,
        use_mock_llm: bool = False,
        max_tokens: int = 500,
        # --- Optional: pass other LlmModel args if needed ---
        # temperature: float = 0.7, # Example
    ):
        """
        Initializes the FileLocalizer.

        Args:
            problem_statement: The description of the problem to solve.
            root_dir: The root directory of the repository to analyze.
            api_key: API key for the LLM service. Passed to LlmModel.
                     Defaults to None (LlmModel might use environment variables).
            model: The specific LLM model name to use. Passed to LlmModel.
                   Defaults to None (LlmModel might have its own default).
            base_url: The base URL for the LLM API endpoint. Passed to LlmModel.
                      Defaults to None (LlmModel might use default provider URL).
            use_mock_llm: If True, use a mock LLM for testing. Passed to LlmModel.
                          Defaults to False.
            max_tokens: The maximum number of tokens for the LLM response.
                        Passed to LlmModel. Defaults to 500.
            # temperature: Temperature setting for the LLM. Passed to LlmModel.
        """
        self.problem_statement = problem_statement
        self.root_dir = Path(root_dir)
        self.exclude_dirs = ['.git', '.venv', 'venv', 'env', 'virtualenv', 'lib64', 'node_modules', '__pycache__']
        self.structure = self._get_project_structure()

        # Initialize LlmModel using the arguments passed to this constructor
        self.llm = LlmModel(
            api_key=api_key,            # Use the api_key argument
            model=model,                # Use the model argument
            base_url=base_url,          # Use the base_url argument
            use_mock_llm=use_mock_llm,  # Use the use_mock_llm argument
            max_tokens=max_tokens,      # Use the max_tokens argument
            # temperature=temperature,  # Pass other args if needed
        )
        # You don't necessarily need to store api_key, model etc. as self.llm_api_key
        # unless you need them elsewhere in FileLocalizer *outside* of self.llm.
        # Passing them directly during LlmModel initialization is sufficient.

    def _get_project_structure(self):
        """Generate a representation of the project structure."""
        structure = {}
        root_path = Path(self.root_dir).resolve() # Use resolved absolute path for walk

        for root, dirs, files in os.walk(root_path, topdown=True):
            current_path = Path(root)
            # Filter directories
            dirs[:] = [d for d in dirs if d not in self.exclude_dirs and not d.startswith('.')]
            # Filter files
            files = [f for f in files if not f.startswith('.')]

            # Calculate relative path from the original root_dir
            try:
                # Ensure rel_path is calculated relative to the initial root_dir path object
                rel_path_str = str(current_path.relative_to(self.root_dir))
                if rel_path_str == '.':
                    rel_path_str = ''
            except ValueError:
                 # Should not happen if os.walk starts within root_dir, but handle defensively
                 logger.critical(f"Could not compute relative path for {current_path}")
                 continue


            structure[rel_path_str] = {
                'files': sorted(files), # Sort for consistent output
                'dirs': sorted(dirs)    # Sort for consistent output
            }

        return structure # Returns dict { 'rel/path': {'files': [...], 'dirs': [...]}}


    def _format_structure(self):
        """Format the project structure for display in the prompt."""
        lines = []
        # Sort keys (paths) for consistent structure representation
        sorted_paths = sorted(self.structure.keys(), key=lambda x: (x.count(os.sep), x))

        path_map = {path: self.structure[path] for path in sorted_paths}
        processed_dirs = set()

        def add_level(current_rel_path_str, level=0):
            indent = '  ' * level
            base_name = os.path.basename(current_rel_path_str) if current_rel_path_str else "." # Display root as '.'

            # Add directory entry if it has content or is the root
            if current_rel_path_str in path_map or current_rel_path_str == '':
                 # Display directory name (add '/' for non-root dirs)
                dir_display_name = f"{base_name}/" if current_rel_path_str else base_name
                lines.append(f"{indent}{dir_display_name}")

                entry = path_map.get(current_rel_path_str, {'files': [], 'dirs': []}) # Get entry safely

                # Add files in this directory
                for f in entry['files']:
                    lines.append(f"{indent}  {f}")

                # Recursively add subdirectories
                processed_dirs.add(current_rel_path_str)
                for d in entry['dirs']:
                    # Construct the full relative path for the subdirectory
                    sub_dir_rel_path = os.path.join(current_rel_path_str, d) if current_rel_path_str else d
                    if sub_dir_rel_path not in processed_dirs: # Avoid redundant processing if structure is complex
                         add_level(sub_dir_rel_path, level + 1)

            # Handle directories that might appear in structure keys but not as subdirs of processed ones
            # (This part might be redundant with the sorted_paths approach but adds robustness)
            elif current_rel_path_str not in processed_dirs:
                 lines.append(f"{indent}{base_name}/") # Add directory entry even if empty in structure map
                 processed_dirs.add(current_rel_path_str)


        # Start formatting from the root ('')
        add_level('')

        # Ensure all paths from the structure are included (handles potentially disconnected structure parts)
        # This is less likely with the os.walk approach but good for robustness
        for path_str in sorted_paths:
             if path_str not in processed_dirs and path_str != '':
                  # Calculate level based on path depth
                  level = path_str.count(os.sep)
                  # Find parent to indent correctly (simplified logic here)
                  # This part needs careful implementation if disconnected paths are expected.
                  # For standard os.walk, the initial add_level('') call should cover everything.
                  pass # Assuming add_level from root covers all connected parts

        return '\n'.join(lines)


    def _parse_model_output(self, content):
        """Parse the model output to extract file paths."""
        logger.debug(f"Parsing LLM output: {content!r}")
        if not content:
            return []

        # Extract content between triple backticks if they exist
        if '```' in content:
            start = content.find('```')
            if start == -1:
                # Fallback: Maybe backticks are missing? Try parsing whole content.
                file_content = content.strip()
            else:
                end = content.find('```', start + 3)
                if end == -1:
                    # Only opening backticks found, take content after it
                    file_content = content[start+3:].strip()
                else:
                    # Both backticks found
                    file_content = content[start+3:end].strip()
        else:
            # No backticks, assume the whole content is the list
            file_content = content.strip()

        # Split by new lines and filter out empty lines
        suggested_files = [line.strip() for line in file_content.splitlines() if line.strip()] # Use splitlines()

        if not suggested_files:
            return []

        # Handle the specific "No relevant files found." message
        if len(suggested_files) == 1 and suggested_files[0].lower() == "no relevant files found.":
            return []

        # Handle the "No additional relevant files." message
        if len(suggested_files) == 1 and suggested_files[0].lower() == "no additional relevant files.":
            return []

        # Basic validation: rudimentary check if lines look like paths (contain '/', '.', or alphanumeric)
        # This is optional and can be refined.
        valid_files = []
        for file_path in suggested_files:
            # Add more robust path validation if needed
            if '/' in file_path or '.' in file_path or file_path.isalnum():
                 # Normalize path separators for consistency (optional but good practice)
                 valid_files.append(os.path.normpath(file_path))
            else:
                logger.warning(f"Ignoring potentially invalid line from LLM output: '{file_path}'")


        logger.debug(f"Parsed valid files: {valid_files}")
        return valid_files

    def _find_matching_files(self, suggested_files):
        """
        Find actual files that match the suggested paths relative to the root_dir.

        Args:
            suggested_files: List of file paths suggested by the model

        Returns:
            List of matching file paths (as strings relative to root_dir) that actually exist
        """
        existing_files = []
        logger.debug(f"Finding matching files for suggested list: {suggested_files}")
        for file_path_str in suggested_files:
            # Ensure the path is treated as relative to the root directory
            # Path() handles joining correctly.
            full_path = self.root_dir.resolve() / file_path_str
            try:
                if full_path.exists() and full_path.is_file():
                    # Return the path relative to the original root_dir
                    relative_path_str = str(Path(file_path_str)) # Keep original relative form
                    existing_files.append(relative_path_str)
                else:
                    logger.warning(f"Suggested file '{file_path_str}' does not exist or is not a file in the repository at '{full_path}'.")
            except OSError as e:
                logger.critical(f"Error checking suggested file '{file_path_str}': {e}")


        logger.debug(f"Matched existing files: {existing_files}")
        return existing_files

    def _get_file_summaries(self, file_paths, project_name):
        """
        Get summaries for the given file paths using the get_file_summary service.

        Args:
            file_paths: List of file paths to get summaries for
            project_name: The name of the project

        Returns:
            List of dictionaries containing file paths and summaries
        """
        # Require project name for summaries
        if not project_name:
            logger.error("Project name is required to retrieve file summaries.")
            return []
        logger.info(f"Fetching file summaries for files: {file_paths}")
        try:
            import asyncio
            from app.services.get_file_summary_service import get_file_summaries

            # Create an event loop and run the async function in it
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            summaries = loop.run_until_complete(get_file_summaries(file_paths, project_name))
            loop.close()
            logger.info(f"Retrieved file summaries for files: {[s.get('file_path', 'unknown') for s in summaries]}")
            return summaries
        except Exception as e:
            logger.error(f"Error getting file summaries: {e}")
            return []

    def _format_file_summaries(self, summaries):
        """
        Format file summaries for display in the prompt.

        Args:
            summaries: List of dictionaries with keys 'file_path' and 'summary'

        Returns:
            Formatted string of file paths and summaries
        """
        logger.debug(f"Formatting file summaries, summaries count: {len(summaries)}")
        if not summaries:
            return "No file summaries available."

        formatted = []
        for summary in summaries:
            file_path = summary.get('file_path', 'Unknown file')
            summary_text = summary.get('summary', 'No summary available')
            formatted.append(f"File: {file_path}\nSummary: {summary_text}\n")

        logger.debug(f"Formatted summaries: {formatted}")
        return "\n".join(formatted)

    def localize_files(self, project_name=None, mock_response=None, mock_additional_response=None):
        """
        Identify relevant files for the given problem statement using the LLM in a two-step process.

        Args:
            project_name: Optional project name for retrieving file summaries
            mock_response: Optional mock response string for testing first LLM call
            mock_additional_response: Optional mock response for second LLM call

        Returns:
            Tuple of (list_of_found_files, list_of_prompts_used)
        """
        # First phase: get initial relevant files
        structure_display = self._format_structure()
        first_prompt = self.obtain_relevant_files_prompt.format(
            problem_statement=self.problem_statement,
            structure=structure_display
        )
        logger.info("First Phase LLM Prompt Sending")
        logger.info(first_prompt)

        if mock_response is not None:
            logger.info("Using Mock Response for first phase")
            first_model_output = mock_response
        elif self.llm.use_mock_llm:
            logger.info("Using LlmModel Mock Generation for first phase")
            first_model_output = self.llm.send_prompt(first_prompt)
            logger.info(f"Mock Output:\n{first_model_output}")
        else:
            logger.info("Calling LLM for first phase")
            try:
                first_model_output = self.llm.send_prompt(first_prompt)
                logger.info("First Phase LLM Response Received")
                logger.info(first_model_output)
            except Exception as e:
                logger.critical(f"Error calling LLM for first phase: {e}")
                return [], [first_prompt]

        # Parse the first model output
        first_suggested_files = self._parse_model_output(first_model_output)
        logger.debug(f"First phase suggested files: {first_suggested_files}")
        # Verify suggested files exist
        first_found_files = self._find_matching_files(first_suggested_files)
        logger.info(f"First phase found existing files: {first_found_files}")

        # If no files found, skip summary-based refinement
        if not first_found_files:
            logger.warning(f"Skipping second phase: no initial files found")
            return first_found_files, [first_prompt]

        # Second phase: get file summaries and find additional files
        summaries = self._get_file_summaries(first_found_files, project_name)
        logger.info(f"Received file summaries: {summaries}")


        # Format summaries for the second prompt
        formatted_summaries = self._format_file_summaries(summaries)
        logger.debug(f"Formatted file summaries to send to LLM: {formatted_summaries}")

        # Create the refined prompt with file summaries
        second_prompt = self.refine_relevant_files_prompt.format(
            file_summaries=formatted_summaries,
            problem_statement=self.problem_statement,
            structure=structure_display
        )

        logger.info("Second Phase LLM Prompt Sending")
        logger.info(second_prompt)

        if mock_additional_response is not None:
            logger.info("Using Mock Response for second phase")
            second_model_output = mock_additional_response
        elif self.llm.use_mock_llm:
            logger.info("Using LlmModel Mock Generation for second phase")
            second_model_output = self.llm.send_prompt(second_prompt)
            logger.info(f"Mock Output:\n{second_model_output}")
        else:
            logger.info("Calling LLM for second phase")
            try:
                second_model_output = self.llm.send_prompt(second_prompt)
                logger.info("Second Phase LLM Response Received")
                logger.info(second_model_output)
            except Exception as e:
                logger.critical(f"Error calling LLM for second phase: {e}")
                return first_found_files, [first_prompt, second_prompt]

        # Parse the second model output
        additional_suggested_files = self._parse_model_output(second_model_output)
        logger.debug(f"Second phase suggested file paths: {additional_suggested_files}")
        # Verify additional suggested files exist
        additional_found_files = self._find_matching_files(additional_suggested_files)
        logger.info(f"Second phase found existing additional files: {additional_found_files}")

        # Prioritize top 3 from first_found_files and top 2 from additional_found_files
        prioritized = []
        for f in first_found_files[:3]:
            if f not in prioritized:
                prioritized.append(f)
        for f in additional_found_files[:2]:
            if f not in prioritized:
                prioritized.append(f)
        # Combine both sets of files, preserving order and removing duplicates
        combined = first_found_files + additional_found_files
        remaining = []
        for f in combined:
            if f not in prioritized and f not in remaining:
                remaining.append(f)
        all_files = prioritized + remaining

        logger.info(f"All relevant files: {all_files}")
        return all_files, [first_prompt, second_prompt]
