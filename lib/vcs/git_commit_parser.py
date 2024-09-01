import git
import json

class GitCommitParser:
    def __init__(self, json_data):
        """
        Initialize with a JSON object in the same format as what `get_commits_up_to_depth_or_oid` returns.
        """
        self.commits = json_data
        # Get the first OID from the initialized JSON and assign it to self.stop_oid
        if self.commits:
            self.stop_oid = self.commits[0]['oid']
        else:
            self.stop_oid = None

    def get_commit_info_at_depth(self, repo, depth):
        try:
            # Get the total number of commits in the repository
            total_commits = repo.git.rev_list('--count', 'HEAD')
            if depth >= int(total_commits):
                return None  # Depth exceeds the number of commits, return None

            # Get the commit object at the given depth
            commit = repo.commit(f'HEAD~{depth}')

            # Get the commit message
            message = commit.message.strip()

            # Get the list of files changed in the commit
            files = []
            for diff in commit.diff(commit.parents[0] if commit.parents else None):
                files.append(diff.a_path)

            return {
                "oid": commit.hexsha,
                "message": message,
                "files": files
            }

        except Exception as e:
            print(f"Error processing commit at depth {depth}: {e}")
            return None

    def get_commits_up_to_depth_or_oid(self, repo_path, max_depth):
        try:
            repo = git.Repo(repo_path)
            commits = []
            for i in range(max_depth):
                commit_info = self.get_commit_info_at_depth(repo, i)
                if commit_info:
                    if commit_info['oid'] == self.stop_oid:
                        break  # Stop just before processing the specified OID
                    commits.append(commit_info)
                else:
                    break  # Stop if we've reached an invalid commit or error occurs

            return commits

        except Exception as e:
            print(f"Error accessing the repository: {e}")
            return []

    def add_commits_to_log(self, repo_path, max_depth):
        """
        Adds the result of `get_commits_up_to_depth_or_oid` to the beginning of the commits log JSON object.
        """
        new_commits = self.get_commits_up_to_depth_or_oid(repo_path, max_depth)
        self.commits = new_commits + self.commits  # Prepend the new commits to the existing log
