import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import HomeGrid from "../components/HomeGrid";
import { ErrorBanner } from "../components/ui";
import { useLiveRefresh } from "../live";

const TOPICS = [
  { id: "all", label: "All" },
  { id: "sport", label: "Sports" },
  { id: "dorm", label: "Dorm" },
  { id: "scoop", label: "Scoop" },
];

export default function Home() {
  const [topic, setTopic] = useState("all");
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setReady(false);
    api
      .listNewsArticles({ topic, page: 1, pageSize: 20 })
      .then((data) => {
        if (cancelled) return;
        setItems(data.items);
        setTotal(data.total);
        setError(null);
      })
      .catch((err) => {
        if (cancelled) return;
        setItems([]);
        setTotal(0);
        setError(err);
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
          setReady(true);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [topic]);

  const refreshHome = useCallback(
    () =>
      api.listNewsArticles({ topic, page: 1, pageSize: 20 }).then((data) => {
        setItems(data.items);
        setTotal(data.total);
        setError(null);
      }),
    [topic],
  );

  useLiveRefresh(ready, refreshHome);

  return (
    <div>
      <ErrorBanner error={error} />
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-black pt-5 pb-3" aria-label="News categories">
        <div className="flex flex-wrap gap-x-6 gap-y-2">
          {TOPICS.map((item) => (
            <button key={item.id} type="button" aria-pressed={topic === item.id} onClick={() => setTopic(item.id)} className={`font-sans text-[11px] font-semibold uppercase tracking-[0.16em] ${topic === item.id ? "text-[#1A4FBF]" : "text-neutral-500 hover:text-black"}`}>
              {item.label}
            </button>
          ))}
        </div>
        <span className="font-sans text-xs text-neutral-500">{total} stories</span>
      </div>
      <HomeGrid items={items} total={total} loading={loading} />
    </div>
  );
}
