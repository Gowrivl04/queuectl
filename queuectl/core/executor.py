"""Command execution with timeouts."""
import asyncio
import shlex
from typing import Optional, Tuple


class ExecutionError(Exception):
    """Raised when command execution fails."""
    pass


class CommandExecutor:
    """Execute shell commands with timeout."""
    
    def __init__(self, timeout: int = 300):
        """Initialize executor with default timeout."""
        self.timeout = timeout

    async def execute(self, command: str) -> Tuple[Optional[str], Optional[str], int]:
        """Execute a shell command and return stdout, stderr and duration."""
        start = asyncio.get_event_loop().time()
        
        try:
            # Split command into args, respecting quotes
            args = shlex.split(command)
            
            # Create subprocess
            process = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                # Wait for completion with timeout
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.timeout
                )
            except asyncio.TimeoutError:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
                raise ExecutionError(f"Command timed out after {self.timeout} seconds")
                
            duration = int((asyncio.get_event_loop().time() - start) * 1000)
            
            if process.returncode != 0:
                raise ExecutionError(
                    f"Command failed with exit code {process.returncode}\n"
                    f"stderr: {stderr.decode('utf-8', errors='replace')}"
                )
                
            return (
                stdout.decode("utf-8", errors="replace"),
                stderr.decode("utf-8", errors="replace"),
                duration
            )
            
        except FileNotFoundError:
            raise ExecutionError(f"Command not found: {args[0]}")
            
        except Exception as e:
            raise ExecutionError(f"Failed to execute command: {str(e)}")