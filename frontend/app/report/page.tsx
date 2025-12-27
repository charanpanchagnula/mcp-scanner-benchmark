"use client";
import { Suspense, useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { getScan, ScanResult, ScannerOutput, Vulnerability, CategoryEvaluation } from '@/lib/api';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { CheckCircle2, AlertOctagon, Trophy, Code, Activity, ServerCrash, Loader2, Search } from "lucide-react";
import { Button } from '@/components/ui/button';

function ScanPageContent() {
    const searchParams = useSearchParams();
    const id = searchParams.get('id');
    const [scan, setScan] = useState<ScanResult | null>(null);
    const [loading, setLoading] = useState(true);
    const [selectedScanner, setSelectedScanner] = useState<string | null>(null);

    useEffect(() => {
        if (!id) return;

        let intervalId: NodeJS.Timeout;

        const fetchScan = async () => {
            try {
                const data = await getScan(id as string);
                setScan(data);

                // If completed or error, stop polling
                if (data.status === 'completed' || data.status === 'error') {
                    if (intervalId) clearInterval(intervalId);
                }
            } catch (error) {
                console.error("Failed to fetch scan:", error);
            } finally {
                setLoading(false);
            }
        };

        // Initial fetch
        fetchScan();

        // Poll every 3 seconds if status is pending
        intervalId = setInterval(() => {
            if (scan && (scan.status === 'completed' || scan.status === 'error')) {
                clearInterval(intervalId);
                return;
            }
            fetchScan();
        }, 3000);

        return () => clearInterval(intervalId);
    }, [id]);

    if (loading) return (
        <div className="flex flex-col items-center justify-center min-h-[60vh] space-y-4">
            <div className="animate-spin rounded-full h-12 w-12 border-4 border-indigo-100 border-t-indigo-600"></div>
            <p className="text-slate-500 font-medium animate-pulse">Loading analysis report...</p>
        </div>
    );

    if (!scan) return (
        <div className="flex flex-col items-center justify-center min-h-[60vh] text-slate-500">
            <div className="bg-slate-100 p-4 rounded-full mb-4">
                <Search className="h-8 w-8 text-slate-400" />
            </div>
            <h2 className="text-xl font-bold text-slate-900">Scan not found</h2>
            <p className="mt-2">The requested benchmark report does not exist or has been deleted.</p>
        </div>
    );

    // IN PROGRESS STATE
    if (scan.status === 'pending' || scan.status === 'running') {
        return (
            <div className="flex flex-col items-center justify-center h-[60vh] space-y-6 text-center">
                <div className="relative">
                    <div className="absolute inset-0 bg-indigo-100 rounded-full animate-ping opacity-75"></div>
                    <div className="relative bg-white p-4 rounded-full shadow-lg border border-indigo-100">
                        <Loader2 className="h-8 w-8 text-indigo-600 animate-spin" />
                    </div>
                </div>
                <div>
                    <h2 className="text-2xl font-bold text-slate-900">Benchmark in Progress</h2>
                    <p className="text-slate-500 mt-2 max-w-md mx-auto">
                        We are currently cloning the repository, running static analysis, and fuzzing the MCP server endpoints.
                    </p>
                </div>
                <div className="bg-slate-50 border rounded-lg p-6 w-full max-w-md text-left shadow-sm">
                    <div className="flex items-center gap-2 text-sm font-semibold text-slate-700 mb-3">
                        <Activity className="h-4 w-4 text-indigo-500" /> Live Status
                    </div>
                    <div className="space-y-2 text-xs text-slate-500 font-mono">
                        <div className="flex justify-between border-b pb-1">
                            <span>Target:</span>
                            <span className="text-slate-700">{scan.target}</span>
                        </div>
                        <div className="flex justify-between border-b pb-1">
                            <span>Type:</span>
                            <span className="text-indigo-600 font-bold uppercase">{scan.scan_type || 'static'}</span>
                        </div>
                        <p className="text-indigo-600 animate-pulse pt-2">Running scanners and evaluation agent...</p>
                    </div>
                </div>
            </div>
        );
    }

    // Use scan.scan_type to determine what to show. No toggling allowed.
    const reportType = scan.scan_type === 'dynamic' ? 'dynamic' : 'static';

    // COMPLETED STATE
    const evaluation = scan.evaluation && !scan.evaluation.skipped
        ? (reportType === 'static' ? scan.evaluation.static : scan.evaluation.dynamic)
        : null;

    // Safety check for skipped evaluation context
    const isSkipped = scan.evaluation?.skipped;

    return (
        <div className="space-y-8">
            {/* Header */}
            <div className="flex flex-col gap-4 border-b pb-6">
                <div>
                    <div className="flex items-center gap-3">
                        <h1 className="text-3xl font-bold tracking-tight text-slate-900">
                            {reportType === 'dynamic' ? 'Dynamic Analysis Report' : 'Static Analysis Report'}
                        </h1>
                        <span className={`px-3 py-1 rounded-full text-sm font-medium ${scan.status === 'completed' ? 'bg-green-100 text-green-700' :
                            scan.status === 'error' ? 'bg-red-100 text-red-700' :
                                'bg-yellow-100 text-yellow-700'
                            }`}>
                            {scan.status.toUpperCase()}
                        </span>
                    </div>
                    <p className="text-slate-500 font-mono text-sm mt-1">
                        {scan.target} @ {scan.branch}
                    </p>
                </div>
            </div>

            {/* Evaluation Summary */}
            {isSkipped ? (
                <Card className="border-yellow-200 bg-yellow-50/50 shadow-sm border-none ring-1 ring-yellow-100">
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2 text-yellow-800">
                            <AlertOctagon className="h-6 w-6" />
                            AI Evaluation Skipped
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <p className="text-slate-700 text-sm">
                            The AI agent evaluation was skipped. Reason: <span className="font-mono bg-yellow-100 px-1 rounded text-xs">{scan.evaluation?.reason}</span>
                        </p>
                        <p className="text-xs text-slate-500 mt-2">
                            To enable agentic evaluation, please configure the <code className="text-[10px] bg-slate-100 px-1 rounded">DEEPSEEK_API_KEY</code> environment variable.
                        </p>
                    </CardContent>
                </Card>
            ) : evaluation ? (
                <EvaluationSection result={evaluation} />
            ) : (
                <div className="text-center p-12 bg-white rounded-2xl border-2 border-dashed border-slate-100">
                    <p className="text-slate-500 font-medium">No verified evaluation findings for {reportType} analysis.</p>
                </div>
            )}

            {/* Scanner Details Tabs */}
            <div className="space-y-6">
                <div className="flex items-center justify-between">
                    <h2 className="text-xl font-bold flex items-center gap-2 text-slate-900">
                        {reportType === 'static' ? <Code className="h-5 w-5 text-indigo-500" /> : <Activity className="h-5 w-5 text-orange-500" />}
                        Scanner Breakdown
                    </h2>
                </div>

                <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-hide">
                    {Object.keys(scan.scanner_results)
                        .filter(name => scan.scanner_results[name][reportType])
                        .map(name => {
                            const result = scan.scanner_results[name][reportType];
                            const count = result?.vulnerabilities?.length || 0;
                            const isSelected = selectedScanner === name || (!selectedScanner && name === Object.keys(scan.scanner_results).filter(n => scan.scanner_results[n][reportType])[0]);
                            return (
                                <Button
                                    key={name}
                                    variant={isSelected ? "default" : "outline"}
                                    onClick={() => setSelectedScanner(name)}
                                    className={`rounded-full px-6 transition-all ${isSelected
                                        ? (reportType === 'static' ? 'bg-indigo-600 hover:bg-indigo-700' : 'bg-orange-600 hover:bg-orange-700')
                                        : 'hover:bg-slate-50 border-slate-200 text-slate-600'}`}
                                >
                                    {name} <span className={`ml-2 px-1.5 py-0.5 rounded-full text-[10px] ${isSelected ? 'bg-white/20' : 'bg-slate-100'}`}>{count}</span>
                                </Button>
                            );
                        })}
                </div>

                {selectedScanner ? (
                    <ScannerDetailResult
                        result={scan.scanner_results[selectedScanner][reportType]}
                        scannerName={selectedScanner}
                        repoUrl={scan.target}
                        branch={scan.branch}
                    />
                ) : Object.keys(scan.scanner_results).filter(n => scan.scanner_results[n][reportType]).length > 0 ? (
                    (() => {
                        const firstScanner = Object.keys(scan.scanner_results).filter(n => scan.scanner_results[n][reportType])[0];
                        return (
                            <ScannerDetailResult
                                result={scan.scanner_results[firstScanner][reportType]}
                                scannerName={firstScanner}
                                repoUrl={scan.target}
                                branch={scan.branch}
                            />
                        );
                    })()
                ) : (
                    <Card className="border-none shadow-sm ring-1 ring-slate-100 bg-white p-12 text-center text-slate-500">
                        No {reportType} scanners were executed for this benchmark.
                    </Card>
                )}
            </div>
        </div>
    );
}


export default function ScanPage() {
    return (
        <Suspense fallback={<div>Loading...</div>}>
            <ScanPageContent />
        </Suspense>
    );
}

function EvaluationSection({ result }: { result: CategoryEvaluation }) {
    const scores = Object.entries(result.scores || {}).sort((a, b) => b[1] - a[1]);

    return (
        <div className="space-y-6">
            <div className="grid gap-6 md:grid-cols-3">
                <Card className="md:col-span-2 border-indigo-200 bg-indigo-50/50 shadow-sm">
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2 text-indigo-900">
                            <Trophy className="h-6 w-6 text-yellow-500" />
                            Winner: <span className="text-indigo-700 underline decoration-wavy">{result.winner}</span>
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <p className="text-slate-700 leading-relaxed">{result.summary}</p>

                        {result.best_features && result.best_features.length > 0 && (
                            <div className="pt-2">
                                <h4 className="font-bold text-xs uppercase tracking-wider text-slate-500 mb-3 flex items-center gap-2">
                                    <CheckCircle2 className="h-3.5 w-3.5 text-green-500" /> Winning Factors
                                </h4>
                                <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-slate-700">
                                    {result.best_features.map((f, i) => (
                                        <li key={i} className="text-sm flex items-start gap-2">
                                            <span className="h-1.5 w-1.5 rounded-full bg-indigo-400 mt-1.5 flex-shrink-0" />
                                            {f}
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        )}
                    </CardContent>
                </Card>

                <Card className="border-none shadow-sm ring-1 ring-slate-100">
                    <CardHeader>
                        <CardTitle className="text-lg">Scanner Rankings</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        {result.rankings && result.rankings.map((rank, i) => (
                            <div key={i} className="space-y-1.5">
                                <div className="flex items-center justify-between text-sm">
                                    <div className="flex items-center gap-2">
                                        <span className={`w-5 h-5 flex items-center justify-center rounded-full text-[10px] font-bold ${i === 0 ? 'bg-yellow-100 text-yellow-700' : 'bg-slate-100 text-slate-500'}`}>
                                            {i + 1}
                                        </span>
                                        <span className="font-semibold text-slate-700">{rank.scanner}</span>
                                    </div>
                                    <span className="font-black text-indigo-600 font-mono">{rank.score}%</span>
                                </div>
                                <div className="h-1.5 w-full bg-slate-100 rounded-full overflow-hidden">
                                    <div
                                        className={`h-full rounded-full transition-all duration-1000 ${i === 0 ? 'bg-indigo-500' : 'bg-slate-400'}`}
                                        style={{ width: `${rank.score}%` }}
                                    />
                                </div>
                            </div>
                        ))}
                    </CardContent>
                </Card>
            </div>

            {/* AI Performance Matrix */}
            <Card className="border-none shadow-lg bg-white overflow-hidden">
                <div className="bg-slate-900 px-6 py-4 flex items-center justify-between">
                    <h3 className="text-white font-bold flex items-center gap-2">
                        <Activity className="h-4 w-4 text-indigo-400" /> AI Performance Matrix
                    </h3>
                    <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Confidence-weighted scoring</span>
                </div>
                <CardContent className="p-6">
                    <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
                        {scores.map(([name, score]) => (
                            <div key={name} className="flex flex-col items-center gap-3 p-4 rounded-2xl bg-slate-50 border border-slate-100 group hover:border-indigo-200 hover:bg-white transition-all">
                                <div className="relative h-24 w-24">
                                    <svg className="h-full w-full" viewBox="0 0 36 36">
                                        <path
                                            className="text-slate-100 stroke-current"
                                            strokeWidth="3"
                                            fill="none"
                                            d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                                        />
                                        <path
                                            className="text-indigo-600 stroke-current transition-all duration-1000 ease-out"
                                            strokeWidth="3"
                                            strokeDasharray={`${score}, 100`}
                                            strokeLinecap="round"
                                            fill="none"
                                            d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                                        />
                                        <text x="18" y="20.35" className="font-black text-[7px] text-slate-900" textAnchor="middle">{score}%</text>
                                    </svg>
                                </div>
                                <div className="text-center">
                                    <p className="font-bold text-slate-900 group-hover:text-indigo-600 transition-colors uppercase tracking-tight text-xs">{name}</p>
                                    <p className="text-[10px] text-slate-400 font-medium">Holistic Performance</p>
                                </div>
                            </div>
                        ))}
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}

function ScannerDetailResult({ result, scannerName, repoUrl, branch }: { result: ScannerOutput | undefined, scannerName: string, repoUrl: string, branch: string }) {
    if (!result) return <div>No data for {scannerName}</div>;

    if (result.error) {
        return (
            <Card className="border-red-200 bg-red-50">
                <CardContent className="pt-6">
                    <div className="flex items-center gap-2 text-red-700 font-semibold mb-2">
                        <ServerCrash className="h-5 w-5" /> Scan Error
                    </div>
                    <pre className="text-sm text-red-600 whitespace-pre-wrap">{result.error}</pre>
                </CardContent>
            </Card>
        );
    }

    const severityOrder: Record<string, number> = {
        'critical': 0,
        'high': 1,
        'medium': 2,
        'low': 3,
        'info': 4
    };

    const vulns = [...(result.vulnerabilities || [])].sort((a, b) => {
        const orderA = severityOrder[(a.severity || 'medium').toLowerCase()] ?? 10;
        const orderB = severityOrder[(b.severity || 'medium').toLowerCase()] ?? 10;
        return orderA - orderB;
    });

    const getGithubLink = (v: Vulnerability) => {
        if (!repoUrl.startsWith('http')) return null;
        // Clean repo URL (remove .git if present)
        const baseUrl = repoUrl.replace(/\.git$/, '');
        const filePath = v.file_path.startsWith('/') ? v.file_path.substring(1) : v.file_path;
        // If it's the Golden Vulnerable Server, we might need special handling if it's local
        // but the user asked for github links, so we assume remote if target is a URL.
        return `${baseUrl}/blob/${branch}/${filePath}#L${v.start_line}`;
    };

    return (
        <Card>
            <CardHeader className="flex flex-row items-center justify-between">
                <div>
                    <CardTitle>{result.scanner_name || scannerName}</CardTitle>
                    <CardDescription>{vulns.length} vulnerabilities detected</CardDescription>
                </div>
            </CardHeader>
            <CardContent>
                {vulns.length === 0 ? (
                    <div className="text-center py-8 text-slate-500">
                        <CheckCircle2 className="h-12 w-12 text-green-500 mx-auto mb-2" />
                        <p>No vulnerabilities found.</p>
                        {result.raw_output && (
                            <details className="mt-4 text-left">
                                <summary className="cursor-pointer text-xs text-indigo-600">View Raw Output</summary>
                                <pre className="bg-slate-900 text-slate-50 p-4 rounded-md mt-2 text-xs overflow-x-auto">
                                    {result.raw_output}
                                </pre>
                            </details>
                        )}
                    </div>
                ) : (
                    <div className="space-y-4 text-left">
                        {vulns.map((v: Vulnerability, i) => {
                            const githubLink = getGithubLink(v);
                            return (
                                <div key={`${v.id || 'vuln'}-${i}`} className="border rounded-md p-4 space-y-2 hover:bg-slate-50">
                                    <div className="flex items-start justify-between">
                                        <div>
                                            <h4 className="font-semibold text-slate-900">{v.message || "Unknown Issue"}</h4>
                                            <p className="text-xs text-slate-400 mt-1">Rule ID: {v.rule_id}</p>
                                        </div>
                                        <span className={`px-2 py-0.5 rounded text-xs font-bold uppercase ${(v.severity || '').toLowerCase() === 'critical' ? 'bg-purple-100 text-purple-700' :
                                            (v.severity || '').toLowerCase() === 'high' ? 'bg-red-100 text-red-700' :
                                                (v.severity || '').toLowerCase() === 'medium' ? 'bg-orange-100 text-orange-700' :
                                                    'bg-slate-100 text-slate-700'
                                            }`}>
                                            {v.severity || 'Medium'}
                                        </span>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <div className="text-sm text-slate-500 font-mono bg-slate-50 px-2 py-1 rounded inline-block">
                                            {v.file_path}:{v.start_line}
                                        </div>
                                        {githubLink && (
                                            <a
                                                href={githubLink}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className="inline-flex items-center gap-1.5 px-3 py-1 bg-slate-900 border border-slate-700 text-white rounded-md text-[10px] font-bold hover:bg-slate-800 transition-colors shadow-sm ml-auto"
                                            >
                                                <svg className="h-3 w-3 fill-current" viewBox="0 0 24 24">
                                                    <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" />
                                                </svg>
                                                VIEW ON GITHUB
                                            </a>
                                        )}
                                    </div>
                                    {v.code_snippet && (
                                        <pre className="bg-slate-900 text-slate-50 p-3 rounded text-xs overflow-x-auto shadow-inner">
                                            <code>{v.code_snippet}</code>
                                        </pre>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                )}
            </CardContent>
        </Card>
    )
}
