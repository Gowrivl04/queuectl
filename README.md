# queuectl

A lightweight, reliable job queue implementation with SQLite backend using libSQL for persistence.

## Features

- Simple job queue with SQLite persistence
- Automatic job retries with configurable max attempts
- Job priority support
- Delayed job execution (run_at scheduling)
- Job state tracking (pending, processing, completed, failed, dead)
- Web dashboard for monitoring queue status
- Windows and Unix platform support
- Concurrent worker execution
## Installation

```bash
pip install queuectl
```

## Quick Start

1. Set your libSQL database connection:

```bash
# Using a local SQLite file
export QUEUECTL_LIBSQL_DSN="file:local.db"

# Or using a turso.tech hosted database
export QUEUECTL_LIBSQL_DSN="libsql://your-database-url"
```

2. Enqueue a job:

```bash
queuectl enqueue "echo 'Hello from job queue!'"
```
```powershell
queuectl worker
```

4. Add some tasks to try it out:
```powershell
# A simple task
queuectl enqueue "echo 'My first task!'"

# An important task that goes to the front of the line
queuectl enqueue --priority 10 "echo 'Urgent task!'"

# A task that can try up to 5 times if it fails
queuectl enqueue --retries 5 "echo 'Keep trying!'"
```

### Available Dashboard Pages
- `/api/jobs` - See how your tasks are doing
- `/api/workers` - Check on your workers
- `/api/history` - Look back at what's been done 

### Adding Tasks
```powershell
# Basic task
queuectl enqueue "your_command"

# Important task
queuectl enqueue --priority 10 "important_task"

# Task that can retry if it fails
queuectl enqueue --retries 5 "tricky_task"
```

### Checking on Tasks
```powershell
# See details about a specific task
queuectl show <task_id>

# Test the system with multiple tasks
queuectl stress -n 10 -d 100  # Creates 10 test tasks

## Task States 

Your tasks can be in one of these states:
1.  `pending` - Waiting patiently to be worked on
2.  `processing` - Currently being worked on
3.  `completed` - Successfully finished
4.  `failed` - Something went wrong, but we'll try again
5.  `dead` - Failed too many times and won't be retried

## Making It Your Own 

You can customize QueueCtl by setting these environment variables:
- `QUEUECTL_LIBSQL_DSN`: Where to store your tasks
- `QUEUECTL_MAX_RETRIES`: How many times to retry failed tasks
- `QUEUECTL_DASHBOARD_PORT`: Which port to use for the dashboard

## For Developers 

Here's what's under the hood:
-  Async job processing for speed
-  SQLite-based storage that won't lose your data
-  Priority system so important tasks run first
-  Automatic retry when things go wrong
-  Real-time statistics
-  Works on Windows, Mac, and Linux

## Want to Help? 

Feel free to:
-  Report any bugs you find
-  Suggest new features
-  Help improve the code

## Quick Demo Script 

Here's a quick demo script to show it off:

1. Open three terminal windows
2. In terminal 1:
   ```powershell
   $env:QUEUECTL_LIBSQL_DSN="file:local.db"
   queuectl dashboard
   ```

3. In terminal 2:
   ```powershell
   $env:QUEUECTL_LIBSQL_DSN="file:local.db"
   queuectl worker
   ```

4. In terminal 3:
   ```powershell
   $env:QUEUECTL_LIBSQL_DSN="file:local.db"
   # Create some test jobs
   queuectl stress -n 5 -d 100
   # Add a high-priority job
   queuectl enqueue --priority 10 "echo 'VIP task!'"
   ```

## License

MIT - Feel free to use and modify as you like! 📄
