const API_URL = '/api';

export interface Vulnerability {
    id: string;
    rule_id: string;
    message: string;
    severity: string;
    file_path: string;
    start_line: number;
    end_line?: number;
    code_snippet?: string;
    metadata?: Record<string, unknown>;
}

export interface ScannerOutput {
    scanner_name: string;
    vulnerabilities: Vulnerability[];
    raw_output?: string;
    error?: string;
}

export interface Ranking {
    scanner: string;
    score: number;
    reason: string;
}

export interface CategoryEvaluation {
    winner: string;
    runners_up: string[];
    rankings: Ranking[];
    scores: Record<string, number>;
    summary: string;
    best_features: string[];
    missed_vulnerabilities: string[];
}

export interface EvaluationResult {
    static?: CategoryEvaluation;
    dynamic?: CategoryEvaluation;
    skipped?: boolean;
    reason?: string;
}

export interface ScanSummary {
    id: string;
    timestamp: string;
    target: string;
    branch: string;
    scan_type: 'static' | 'dynamic';
    evaluation?: EvaluationResult;
    status: 'pending' | 'running' | 'completed' | 'error';
    error?: string;
}

export interface ScanResult extends ScanSummary {
    scanner_results: Record<string, { static?: ScannerOutput, dynamic?: ScannerOutput }>;
}

export async function getScans(limit: number = 20, offset: number = 0, scanType?: string): Promise<ScanSummary[]> {
    let url = `${API_URL}/scans?limit=${limit}&offset=${offset}`;
    if (scanType) {
        url += `&scan_type=${scanType}`;
    }
    const res = await fetch(url);
    if (!res.ok) throw new Error('Failed to fetch scans');
    return res.json();
}

export async function getScan(id: string): Promise<ScanResult> {
    const res = await fetch(`${API_URL}/scans/${id}`);
    if (!res.ok) throw new Error('Failed to fetch scan');
    return res.json();
}

export async function triggerScan(repo_url: string, branch: string, scan_type: 'static' | 'dynamic' = 'static'): Promise<ScanResult> {
    const res = await fetch(`${API_URL}/scan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ repo_url, branch, scan_type }),
    });
    if (!res.ok) throw new Error('Failed to trigger scan');
    return res.json();
}

export async function getLeaderboard(): Promise<{ static: Record<string, number>, dynamic: Record<string, number> }> {
    const res = await fetch(`${API_URL}/leaderboard`);
    if (!res.ok) throw new Error('Failed to fetch leaderboard');
    return res.json();
}

export async function deleteScan(id: string): Promise<void> {
    const res = await fetch(`${API_URL}/scans/${id}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Failed to delete scan');
}

export async function deleteAllScans(): Promise<void> {
    const res = await fetch(`${API_URL}/scans`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Failed to delete all scans');
}
