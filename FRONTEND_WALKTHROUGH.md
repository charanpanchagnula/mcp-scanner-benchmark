# Frontend Architecture & files Walkthrough

This document provides a detailed, beginner-friendly explanation of the frontend codebase. The project is built with **Next.js 14** (App Router), **React**, **Tailwind CSS**, and **Shadcn UI**.

## Project Structure & Configuration

### `package.json`
*   **Dependencies**: Lists all the libraries used. key ones include:
    *   `next`, `react`, `react-dom`: Core framework.
    *   `lucide-react`: The icon library (e.g., specific icons like `Zap`, `Shield`, `Trophy`).
    *   `tailwindcss`: The styling framework.
    *   `recharts`: For drawing the charts in the report view.
*   **Scripts**:
    *   `dev`: Runs the local development server (localhost:3000).
    *   `build`: Compiles the app for production.

### `lib/api.ts`
This file is the **Bridge** between the Frontend and the Backend. It defines the "shape" of the data (Types) and the functions to fetch it.

*   **Interfaces (TypeScript Definitions)**:
    *   `Vulnerability`: Defines what a security issue looks like (id, severity, message, file_path).
    *   `ScannerOutput`: Shape of a single scanner's result (name, list of vulns, raw output).
    *   `ScanResult`: Shape of the entire benchmark (status, target url, map of scanner results).
    *   `CategoryEvaluation`: Shape of the AI Agent's report (winner text, scores dict, features list).
    *   `ScanSummary`: A lighter version of ScanResult used for the history list (to save bandwidth).
*   **`API_URL`**: Hardcoded to `/api`. In Next.js, this is usually proxied to the backend or matched via the same domain in production.
*   **`getScans()` Function**:
    *   Fetches the list of recent scans.
    *   Accepts `limit` (page size) and `offset` (pagination) arguments.
    *   Accepts `scanType` to filter between 'static' and 'dynamic'.
*   **`triggerScan()` Function**:
    *   Sends a POST request to start a new analysis.
    *   Payload: `{ repo_url, branch, scan_type }`.
*   **`getScan()` Function**:
    *   Fetches the detailed report for a specific ID.
    *   Used by the Report Page.
*   **`getLeaderboard()` Function**:
    *   Fetches the global statistics for the "Leaderboard" tab.

---

## Page Components

### `app/page.tsx` (The Dashboard)
This is the main "Home" page of the application.

*   **"use client" Directive**: The first line tells Next.js this component runs in the browser (needed for interactivity like buttons and state).
*   **State Management (`useState`)**:
    *   `activeTab`: Tracks if user is viewing "Static", "Dynamic", or "Leaderboard".
    *   `repoUrl`, `branch`: Stores the text typed into the input boxes.
    *   `scans`: An array storing the list of historical benchmarks fetched from API.
    *   `loading`: A boolean (true/false) to show spinners when fetching data.
*   **`useEffect` Hook**:
    *   Runs automatically whenever `activeTab` changes.
    *   It clears the current list and fetches fresh data for the selected tab (e.g., switches from Static history to Dynamic history).
*   **`loadData()` Function**:
    *   Smart pagination logic.
    *   It fetches data in chunks (batches of 10).
    *   If `activeTab` is 'leaderboard', it calls `getLeaderboard()` instead of `getScans()`.
*   **`handleScan()` Function**:
    *   Triggered when you click "Start Security Analysis".
    *   Calls `triggerScan()` API.
    *   Optimistically adds the new "Pending" scan to the top of the list so the user sees immediate feedback.
*   **Render Logic (The HTML)**:
    *   **Tabs Section**: Three big buttons (Static/Dynamic/Leaderboard) to switch modes.
    *   **Input Form**: Uses `Card` component to wrap the URL/Branch inputs.
    *   **Info Card**: A colored card (Blue for Static, Orange for Dynamic) explaining what the selected mode does.
    *   **History List**: Maps through the `scans` array and renders a `Card` for each one.
    *   **Leaderboard View**: If tab is leaderboard, it renders a special view with a "Gold/Silver/Bronze" trophy icon logic for the top 3 scanners.

### `app/report/page.tsx` (The Details View)
This page shows the deep-dive analysis for a single benchmark.

*   **`useSearchParams()` Hook**:
    *   Reads the `?id=...` from the browser URL to know which scan to load.
*   **Polling Logic (`useEffect`)**:
    *   If the scan status is "pending" or "running", it sets up a timer (`setInterval`).
    *   Every 3 seconds, it re-fetches the scan data to see if it finished.
    *   Once finished (`completed` or `error`), it clears the timer to stop network traffic.
*   **Conditional Rendering**:
    *   **Loading State**: Shows a spinning loader while fetching initial data.
    *   **Pending State**: Shows a "Live Status" card with a pulsing animation if the scan is still running.
    *   **Completed State**: Shows the full report.
*   **`EvaluationSection` Component**:
    *   Displays the "Winner" card.
    *   Renders the "Winning Factors" list (green checkmarks).
    *   **Performance Matrix**: Renders circular progress charts for each scanner's score using SVG.
*   **`ScannerDetailResult` Component**:
    *   Displays the list of vulnerabilities for a specific selected scanner.
    *   **Severity Sorting**: It sorts issues so "Critical" (Red) ones appear at the top.
    *   **GitHub Linking**: It constructs a clickable link to the exact line of code in the GitHub repository (`.../blob/main/file.py#L10`).
    *   **Code Snippets**: If the scanner provided a snippet, it renders it in a dark-mode code block.
*   **Tabs Logic**:
    *   Dynamically generates tabs for every scanner that produced results.
    *   Allows clicking a scanner name to filter the vulnerability list to just that tool.

## Key UI Components (`components/ui/`)
These are reusable building blocks (from shadcn/ui).

*   **`card.tsx`**: Provides the white box container with shadow and rounded corners. Used everywhere.
*   **`button.tsx`**: Provides the standardized clickable buttons with hover states and variants (default, ghost, outline, destructive).
*   **`input.tsx`**: The text boxes for entering Repo URL and Branch.
