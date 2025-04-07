#!/usr/bin/env python3
import os
import json
from pathlib import Path
from lib.ai.llm_model import LlmModel # Assuming LlmModel is correctly importable

class FileLocalizer:
    """
    A standalone file localizer that identifies relevant files based on a problem statement.
    """

    obtain_relevant_files_prompt = """
Please look through the following GitHub problem description and Repository structure and provide a list of files that one would need to edit to fix the problem.

### GitHub Problem Description ###
{problem_statement}
###

### Repository Structure ###
{structure}
###

Please only provide the full paths relative to the repository root directory and return at most 5 files.
The returned files should be separated by new lines ordered by most to least important and wrapped with triple backticks ```.
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

Please make sure all file paths are relative to the root directory of the provided repository structure.
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
        self.exclude_dirs = ['.git', '.venv', 'venv', 'env', 'virtualenv', 'lib', 'lib64', 'node_modules', '__pycache__']
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
                 print(f"Warning: Could not compute relative path for {current_path}")
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

        # Basic validation: rudimentary check if lines look like paths (contain '/', '.', or alphanumeric)
        # This is optional and can be refined.
        valid_files = []
        for file_path in suggested_files:
            # Add more robust path validation if needed
            if '/' in file_path or '.' in file_path or file_path.isalnum():
                 # Normalize path separators for consistency (optional but good practice)
                 valid_files.append(os.path.normpath(file_path))
            else:
                print(f"Warning: Ignoring potentially invalid line from LLM output: '{file_path}'")


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
                    print(f"Warning: Suggested file '{file_path_str}' does not exist or is not a file in the repository at '{full_path}'.")
            except OSError as e:
                print(f"Warning: Error checking suggested file '{file_path_str}': {e}")


        return existing_files

    def localize_files(self, mock_response=None):
        """
        Identify relevant files for the given problem statement using the LLM.

        Args:
            mock_response: Optional mock response string for testing, bypassing the LLM call.

        Returns:
            Tuple of (list_of_found_files, prompt_used)
        """
        # Generate the prompt
        structure_display = self._format_structure()
        prompt = self.obtain_relevant_files_prompt.format(
            problem_statement=self.problem_statement,
            structure=structure_display
        )

        if mock_response is not None:
            print("--- Using Mock Response ---")
            model_output = mock_response
        elif self.llm.use_mock_llm:
             # Use the mock generation from LlmModel if use_mock_llm was True
             print("--- Using LlmModel Mock Generation ---")
             model_output = self.llm.send_prompt(prompt) # Assuming mock generate works
             print(f"Mock Output:\n{model_output}")
        else:
            # Call the actual LLM via the LlmModel instance
            print("--- Calling LLM ---")
            try:
                # Assuming LlmModel has a method like 'generate' or 'invoke'
                # Adjust the method name and arguments as per LlmModel's interface
                model_output = self.llm.send_prompt(prompt) # Or self.llm.invoke(prompt), etc.
                print("--- LLM Response Received ---")
                # print(model_output) # Optional: print raw response for debugging
            except Exception as e:
                print(f"Error calling LLM: {e}")
                return [], prompt # Return empty list on error

        # Parse the model output
        suggested_files = self._parse_model_output(model_output)
        # Verify suggested files exist
        found_files = self._find_matching_files(suggested_files)

        return found_files, prompt
