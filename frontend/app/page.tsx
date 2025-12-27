"use client";

import { useEffect, useState, useRef } from 'react';
import Link from 'next/link';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { triggerScan, getScans, ScanResult, ScanSummary, deleteScan, deleteAllScans, getLeaderboard } from '@/lib/api';
import { ArrowRight, Play, Loader2, GitBranch, Search, ShieldAlert, CheckCircle2, Trash2, Eraser, Zap, Trophy, Medal, Award } from "lucide-react";

export default function Home() {
  const [activeTab, setActiveTab] = useState<'static' | 'dynamic' | 'leaderboard'>('static');

  // Shared state for forms
  const [repoUrl, setRepoUrl] = useState('');
  const [branch, setBranch] = useState('main');
  const [loading, setLoading] = useState(false);

  // Scans history
  const [scans, setScans] = useState<ScanSummary[]>([]);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(true);

  const LIMIT = 10;
  const [leaderboardData, setLeaderboardData] = useState<{ static: Record<string, number>, dynamic: Record<string, number>, total_scans?: number }>({ static: {}, dynamic: {}, total_scans: 0 });
  const [lbType, setLbType] = useState<'static' | 'dynamic'>('static');

  // To prevent race conditions
  const fetchIdRef = useRef(0);

  useEffect(() => {
    // Reset when tab changes
    setScans([]);
    setOffset(0);
    setHasMore(true);

    // Increment and use ref immediately (sync)
    fetchIdRef.current += 1;
    const targetId = fetchIdRef.current;
    loadData(0, true, targetId);
  }, [activeTab]);

  async function loadData(currentOffset: number = 0, reset: boolean = false, targetFetchId?: number) {
    const activeFetchId = targetFetchId ?? fetchIdRef.current;

    if (activeTab === 'static' || activeTab === 'dynamic') {
      try {
        const data = await getScans(LIMIT + 1, currentOffset, activeTab);
        if (activeFetchId !== fetchIdRef.current) return;

        let filtered = data;
        if (filtered.length > LIMIT) {
          setHasMore(true);
          filtered = filtered.slice(0, LIMIT);
        } else {
          setHasMore(false);
        }

        if (reset) {
          setScans(filtered);
        } else {
          setScans((prev: ScanSummary[]) => [...prev, ...filtered]);
        }
      } catch (e) {
        console.error(e);
      }
    } else if (activeTab === 'leaderboard') {
      try {
        const data = await getLeaderboard();
        if (activeFetchId !== fetchIdRef.current) return;
        setLeaderboardData(data);
      } catch (e) {
        console.error(e);
      }
    }
  }

  async function handleLoadMore() {
    const nextOffset = offset + LIMIT;
    setOffset(nextOffset);
    loadData(nextOffset);
  }

  async function handleScan() {
    if (!repoUrl) return;
    setLoading(true);
    try {
      const type = activeTab === 'dynamic' ? 'dynamic' : 'static';
      const newScan = await triggerScan(repoUrl, branch, type);
      setRepoUrl('');
      setScans((prev: ScanSummary[]) => [newScan, ...prev]);
    } catch (e) {
      console.error(e);
      alert(`Failed to trigger ${activeTab} scan`);
    } finally {
      setLoading(false);
    }
  }

  async function handleDelete(id: string) {
    if (!confirm("Are you sure you want to delete this scan?")) return;
    try {
      await deleteScan(id);
      setScans((prev: ScanSummary[]) => prev.filter(s => s.id !== id));
    } catch (e) {
      alert("Failed to delete scan");
    }
  }

  async function handleClearAll() {
    if (!confirm("Are you sure you want to DELETE ALL scans? This cannot be undone.")) return;
    try {
      await deleteAllScans();
      setScans([]);
      setOffset(0);
      setHasMore(false);
    } catch (e) {
      alert("Failed to delete all scans");
    }
  }

  // Leaderboard helper
  const leaderboard = Object.entries(leaderboardData[lbType] || {}).sort((a, b) => b[1] - a[1]);

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-2">
        <h1 className="text-3xl font-bold tracking-tight text-slate-900">Security Benchmark Dashboard</h1>
        <p className="text-slate-500 text-lg">
          Evaluate MCP security scanners across different analysis vectors.
        </p>
      </div>

      {/* Main Tabs */}
      <div className="flex p-1 bg-slate-100 rounded-xl w-full max-w-2xl shadow-inner border border-slate-200">
        <Button
          variant={activeTab === 'static' ? 'default' : 'ghost'}
          onClick={() => { setActiveTab('static'); setRepoUrl(''); }}
          className={`flex-1 rounded-lg py-6 transition-all ${activeTab === 'static' ? 'bg-white shadow-md text-indigo-600' : 'text-slate-500'}`}
        >
          <Search className="mr-2 h-5 w-5" /> Static Analysis
        </Button>
        <Button
          variant={activeTab === 'dynamic' ? 'default' : 'ghost'}
          onClick={() => { setActiveTab('dynamic'); setRepoUrl(''); }}
          className={`flex-1 rounded-lg py-6 transition-all ${activeTab === 'dynamic' ? 'bg-white shadow-md text-orange-600' : 'text-slate-500'}`}
        >
          <Zap className="mr-2 h-5 w-5" /> Dynamic Fuzzing
        </Button>
        <Button
          variant={activeTab === 'leaderboard' ? 'default' : 'ghost'}
          onClick={() => setActiveTab('leaderboard')}
          className={`flex-1 rounded-lg py-6 transition-all ${activeTab === 'leaderboard' ? 'bg-white shadow-md text-amber-600' : 'text-slate-500'}`}
        >
          <Trophy className="mr-2 h-5 w-5" /> Leaderboard
        </Button>
      </div>

      {activeTab !== 'leaderboard' ? (
        <>
          <div className="grid gap-6 md:grid-cols-2">
            {/* Scanner Form */}
            <Card className={`md:col-span-1 border-none shadow-lg overflow-hidden ring-1 ring-slate-100 transition-all hover:shadow-xl`}>
              <div className={`h-1.5 w-full ${activeTab === 'static' ? 'bg-indigo-500' : 'bg-orange-500'}`} />
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  {activeTab === 'static' ? <ArrowRight className="h-5 w-5 text-indigo-500" /> : <Zap className="h-5 w-5 text-orange-500" />}
                  {activeTab === 'static' ? 'New Static Benchmark' : 'New Dynamic Fuzzing'}
                </CardTitle>
                <CardDescription>
                  {activeTab === 'static'
                    ? 'Code-level vulnerability analysis.'
                    : 'Active probing of MCP server endpoints.'}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium text-slate-700">Repository URL</label>
                  <div className="relative">
                    <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                    <Input
                      placeholder="https://github.com/owner/repo"
                      value={repoUrl}
                      onChange={e => setRepoUrl(e.target.value)}
                      className="pl-9 focus:ring-2 focus:ring-indigo-500 border-slate-200"
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium text-slate-700">Branch</label>
                  <div className="relative">
                    <GitBranch className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                    <Input
                      placeholder="main"
                      value={branch}
                      onChange={e => setBranch(e.target.value)}
                      className="pl-9 focus:ring-2 focus:ring-indigo-500 border-slate-200"
                    />
                  </div>
                </div>

                <Button
                  className={`w-full mt-4 text-white font-bold transition-all shadow-lg py-6 ${activeTab === 'static' ? 'bg-indigo-600 hover:bg-indigo-700 shadow-indigo-100' : 'bg-orange-600 hover:bg-orange-700 shadow-orange-100'}`}
                  onClick={handleScan}
                  disabled={loading || !repoUrl}
                >
                  {loading ? <><Loader2 className="mr-2 h-5 w-5 animate-spin" /> {activeTab === 'static' ? 'Analyzing...' : 'Fuzzing...'} </> : <><Play className="mr-2 h-5 w-5" /> Start Security Analysis</>}
                </Button>
              </CardContent>
            </Card>

            {/* Info Card */}
            <Card className={`md:col-span-1 border-none shadow-lg text-white transition-all hover:shadow-xl ${activeTab === 'static' ? 'bg-gradient-to-br from-indigo-500 to-indigo-700' : 'bg-gradient-to-br from-orange-500 to-amber-600'}`}>
              <CardHeader>
                <CardTitle>{activeTab === 'static' ? 'Static Analysis' : 'Dynamic Fuzzing'}</CardTitle>
                <CardDescription className="text-white/80">
                  {activeTab === 'static' ? 'Heuristic & Semantic scanning.' : 'Behavioral & Injection analysis.'}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="flex items-start gap-3">
                  <div className="p-2 bg-white/10 rounded-lg">
                    <ShieldAlert className="h-6 w-6 text-white" />
                  </div>
                  <div>
                    <p className="font-bold">{activeTab === 'static' ? 'Deep Context' : 'Payload Injection'}</p>
                    <p className="text-sm text-white/80 mt-1">
                      {activeTab === 'static' ? 'Find logic flaws in tool implementations by analyzing data flow and signatures.' : 'Test real-world prompt injection and SSRF scenarios across MCP endpoints.'}
                    </p>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <div className="p-2 bg-white/10 rounded-lg">
                    <CheckCircle2 className="h-6 w-6 text-white" />
                  </div>
                  <div>
                    <p className="font-bold">AI Verification Engine</p>
                    <p className="text-sm text-white/80 mt-1">Findings are cross-validated by our Elite Security Agent powered by DeepSeek.</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* History */}
          <div className="space-y-4 pt-4">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-bold text-slate-900">
                Recent {activeTab === 'static' ? 'Static' : 'Dynamic'} Benchmarks
              </h2>
              {scans.length > 0 && (
                <Button variant="ghost" size="sm" onClick={handleClearAll} className="text-red-500 hover:bg-red-50 font-bold">
                  <Eraser className="mr-2 h-4 w-4" /> Reset Benchmark Data
                </Button>
              )}
            </div>

            <div className="grid gap-4">
              {scans.length === 0 ? (
                <div className="text-center py-16 text-slate-400 bg-white rounded-2xl border-2 border-dashed border-slate-100 shadow-sm flex flex-col items-center gap-4">
                  <Search className="h-12 w-12 text-slate-100" />
                  <p className="font-medium text-lg">No benchmarks found. Start your first analysis above.</p>
                </div>
              ) : (
                scans.map(scan => {
                  const eval_type = activeTab === 'static' ? scan.evaluation?.static : scan.evaluation?.dynamic;
                  const winner = eval_type?.winner;
                  const score = winner ? eval_type?.scores?.[winner] : null;

                  return (
                    <Card key={scan.id} className="hover:shadow-md transition-all group border-none shadow-sm ring-1 ring-slate-100 bg-white hover:ring-indigo-100">
                      <div className="flex items-center justify-between p-6">
                        <div className="space-y-1.5">
                          <div className="flex items-center gap-3">
                            <h3 className="font-black text-slate-800 text-lg">{scan.target.split('/').slice(-2).join('/')}</h3>
                            <span className={`px-2.5 py-0.5 rounded-full text-[10px] uppercase tracking-wider font-black ${scan.status === 'completed' ? 'bg-green-100 text-green-700' :
                              scan.status === 'error' ? 'bg-red-100 text-red-700' :
                                'bg-yellow-100 text-yellow-700'
                              }`}>
                              {scan.status}
                            </span>
                          </div>
                          <div className="flex items-center gap-4 text-xs font-bold text-slate-400 uppercase tracking-tighter">
                            <span className="flex items-center gap-1"><GitBranch className="h-3 w-3" /> {scan.branch}</span>
                            <span>•</span>
                            <span>{new Date(scan.timestamp).toLocaleString()}</span>
                          </div>
                        </div>

                        <div className="flex items-center gap-8">
                          {winner && (
                            <div className="hidden sm:block text-right">
                              <p className="text-[10px] text-slate-400 uppercase font-black tracking-widest mb-1">Top Scanner</p>
                              <div className="flex items-center gap-2 justify-end">
                                <Trophy className="h-4 w-4 text-yellow-500" />
                                <span className={`${activeTab === 'static' ? 'text-indigo-600' : 'text-orange-600'} font-black text-lg`}>
                                  {winner}
                                </span>
                                {score !== null && (
                                  <span className="text-xs bg-slate-100 px-1.5 py-0.5 rounded-md font-mono text-slate-500">
                                    {score}%
                                  </span>
                                )}
                              </div>
                            </div>
                          )}
                          <div className="flex gap-3">
                            <Link href={`/report?id=${scan.id}`}>
                              <Button className={`font-black uppercase tracking-tight text-xs ${activeTab === 'static' ? 'bg-indigo-600 hover:bg-indigo-700' : 'bg-orange-600 hover:bg-orange-700'}`}>
                                View Performance Matrix
                              </Button>
                            </Link>
                            <Button variant="ghost" size="sm" onClick={() => handleDelete(scan.id)} className="text-slate-300 hover:text-red-600 transition-colors">
                              <Trash2 className="h-5 w-5" />
                            </Button>
                          </div>
                        </div>
                      </div>
                    </Card>
                  );
                })
              )}
            </div>

            {hasMore && (
              <div className="flex justify-center pt-8">
                <Button
                  variant="outline"
                  onClick={handleLoadMore}
                  className="px-10 py-6 rounded-full border-2 border-slate-100 font-black uppercase tracking-widest text-xs text-slate-500 shadow-sm hover:shadow-md hover:bg-slate-50 transition-all"
                >
                  Load More benchmarks
                </Button>
              </div>
            )}
          </div>
        </>
      ) : (
        /* Leaderboard Content */
        <div className="space-y-8 animate-in fade-in zoom-in-95 duration-500">
          <div className="flex p-1 bg-slate-200/50 rounded-xl w-fit mx-auto border border-white shadow-inner">
            <Button
              variant={lbType === 'static' ? 'default' : 'ghost'}
              onClick={() => setLbType('static')}
              className={`px-8 py-6 rounded-lg font-bold transition-all ${lbType === 'static' ? 'bg-white shadow-md text-indigo-600' : 'text-slate-500'}`}
            >
              <Search className="mr-2 h-5 w-5" /> Static Leaders
            </Button>
            <Button
              variant={lbType === 'dynamic' ? 'default' : 'ghost'}
              onClick={() => setLbType('dynamic')}
              className={`px-8 py-6 rounded-lg font-bold transition-all ${lbType === 'dynamic' ? 'bg-white shadow-md text-orange-600' : 'text-slate-500'}`}
            >
              <Zap className="mr-2 h-5 w-5" /> Dynamic Leaders
            </Button>
          </div>

          <Card className="border-none shadow-2xl bg-white overflow-hidden max-w-2xl mx-auto ring-1 ring-slate-100">
            <div className={`h-2.5 w-full ${lbType === 'static' ? 'bg-gradient-to-r from-indigo-500 to-indigo-700' : 'bg-gradient-to-r from-orange-500 to-amber-600'}`} />
            <CardContent className="p-0">
              {leaderboard.length === 0 ? (
                <div className="p-24 text-center text-slate-400 flex flex-col items-center gap-6">
                  <div className="bg-slate-50 p-6 rounded-full">
                    <Trophy className="h-16 w-16 text-slate-200" />
                  </div>
                  <div className="space-y-2">
                    <p className="font-black text-xl text-slate-900">No Leaders Yet</p>
                    <p className="text-slate-500">Run security benchmarks to populate the global leaderboard.</p>
                  </div>
                  <Button variant="outline" className="mt-4 font-bold rounded-full px-8" onClick={() => setActiveTab(lbType)}>Run First Benchmark</Button>
                </div>
              ) : (
                <div className="divide-y divide-slate-50">
                  {leaderboard.map(([name, score], index) => (
                    <div key={name} className="flex items-center gap-6 p-10 hover:bg-slate-50/50 transition-all group">
                      <div className="flex-shrink-0 w-16 text-center">
                        {index === 0 ? <Trophy className="h-12 w-12 text-yellow-500 mx-auto drop-shadow-lg animate-bounce duration-slow" /> :
                          index === 1 ? <Medal className="h-10 w-10 text-slate-300 mx-auto" /> :
                            index === 2 ? <Award className="h-10 w-10 text-amber-600 mx-auto" /> :
                              <span className="text-3xl font-black text-slate-100 tracking-tighter italic">#{index + 1}</span>}
                      </div>
                      <div className="flex-1">
                        <div className="flex justify-between items-end mb-4">
                          <h3 className="text-2xl font-black text-slate-800 tracking-tight">{name}</h3>
                          <div className="text-right">
                            <span className="text-2xl font-black text-indigo-600 font-mono tracking-tighter">{Math.round(score)}%</span>
                            <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest mt-1">Holistic Score</p>
                          </div>
                        </div>
                        <div className="h-5 w-full bg-slate-100 rounded-full overflow-hidden shadow-inner p-1">
                          <div
                            className={`h-full rounded-full transition-all duration-[2000ms] shadow-lg ${lbType === 'static' ? 'bg-gradient-to-r from-indigo-500 to-indigo-600' : 'bg-gradient-to-r from-orange-500 to-orange-600'}`}
                            style={{ width: `${score}%` }}
                          />
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          <p className="text-center text-slate-400 text-xs font-medium max-w-md mx-auto leading-relaxed">
            Holistic scores are calculated using a time-weighted moving average across all historical benchmarks for each scanner.
          </p>
        </div>
      )}
    </div>
  );
}
