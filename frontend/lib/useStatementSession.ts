"use client";

// All the data for one uploaded statement, and the actions that change it.
// Every action sends the change to the backend and then reloads,
// so the screen always shows what the backend decided.

import { useEffect, useState } from "react";
import {
  ApiError,
  getCategories,
  getReviewGroups,
  getSummary,
  getTransactions,
  saveAlwaysRule,
  updateTransaction,
  updateTransactions,
  uploadStatement,
} from "./api";
import type { Category, ReviewGroup, Row, Session, Summary } from "./types";

// What the user chose for a Needs Review group.
export interface GroupFix {
  category: string;
  always: boolean; // also save a rule for this merchant
  businessPct?: number; // only for mixed-use categories like Phone & Data
}

// Turns any error into a message we can show.
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === "session_not_found") {
      return "This statement is no longer loaded (the server restarted or the session expired). Please upload it again.";
    }
    return error.message;
  }
  return "Something went wrong. Please try again.";
}

export function useStatementSession() {
  // Data from the backend
  const [categories, setCategories] = useState<Category[]>([]);
  const [session, setSession] = useState<Session | null>(null);
  const [rows, setRows] = useState<Row[]>([]);
  const [reviewGroups, setReviewGroups] = useState<ReviewGroup[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);

  // What is happening right now
  const [loadingCategories, setLoadingCategories] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  // Load the category list once, for the dropdowns.
  useEffect(() => {
    getCategories()
      .then(setCategories)
      .catch((e) => setError(errorMessage(e)))
      .finally(() => setLoadingCategories(false));
  }, []);

  // Reloads rows, review groups and totals from the backend (all three at once).
  async function reload(sessionId: string) {
    const [newRows, newGroups, newSummary] = await Promise.all([
      getTransactions(sessionId),
      getReviewGroups(sessionId),
      getSummary(sessionId),
    ]);
    setRows(newRows);
    setReviewGroups(newGroups);
    setSummary(newSummary);
  }

  async function upload(file: File, taxYear?: number) {
    setUploading(true);
    setError(null);
    setNotice(null);
    try {
      const newSession = await uploadStatement(file, taxYear);
      setSession(newSession);
      await reload(newSession.session_id);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setUploading(false);
    }
  }

  // Runs one change against the backend, then reloads so the screen matches.
  async function saveAndReload(change: (sessionId: string) => Promise<void>) {
    if (!session) return;
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      await change(session.session_id);
      await reload(session.session_id);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setSaving(false);
    }
  }

  function changeCategory(row: Row, category: string) {
    return saveAndReload(async (sessionId) => {
      await updateTransaction(sessionId, row.id, { category: category });
    });
  }

  function changeBusinessPct(row: Row, pct: number) {
    if (!Number.isInteger(pct) || pct < 0 || pct > 100) {
      setError("Business-use % must be a whole number between 0 and 100.");
      return Promise.resolve();
    }
    return saveAndReload(async (sessionId) => {
      await updateTransaction(sessionId, row.id, { business_pct: pct });
    });
  }

  // Applies one category to every row in a Needs Review group.
  function fixReviewGroup(group: ReviewGroup, fix: GroupFix) {
    return saveAndReload(async (sessionId) => {
      if (fix.always) {
        // Save a rule. The backend applies it to all rows from this merchant, now and in later uploads.
        const result = await saveAlwaysRule(sessionId, group.merchant_key, fix.category);
        setNotice(
          `Saved rule: always ${result.rule.merchant_key} as ${result.rule.category} (${result.updated_count} rows updated).`,
        );
        // Mixed-use categories like Phone & Data also need the business-use %.
        if (fix.businessPct !== undefined) {
          await updateTransactions(sessionId, group.transaction_ids, { business_pct: fix.businessPct });
        }
      } else {
        // One request for the whole group: the backend applies it to every row or to none.
        await updateTransactions(sessionId, group.transaction_ids, {
          category: fix.category,
          business_pct: fix.businessPct,
        });
      }
    });
  }

  function startOver() {
    setSession(null);
    setRows([]);
    setReviewGroups([]);
    setSummary(null);
    setNotice(null);
    setError(null);
  }

  return {
    categories,
    session,
    rows,
    reviewGroups,
    summary,
    loadingCategories,
    uploading,
    saving,
    error,
    notice,
    upload,
    changeCategory,
    changeBusinessPct,
    fixReviewGroup,
    startOver,
    showError: setError,
    dismissError: () => setError(null),
  };
}
