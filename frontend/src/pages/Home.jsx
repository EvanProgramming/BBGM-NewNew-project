import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
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
  const [searchParams, setSearchParams] = useSearchParams();
  const requested = searchParams.get("topic");
  const topic = TOPICS.some((item) => item.id === requested) ? requested : "all";
  function selectTopic(next) {
    setSearchParams(next === "all" ? {} : { topic: next });
  }
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
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-black pb-3 pt-5" aria-label="News categories">
        <div className="flex flex-wrap items-center gap-x-1 gap-y-1">
          {TOPICS.map((item) => (
            <button key={item.id} type="button" aria-pressed={topic === item.id} onClick={() => selectTopic(item.id)} className="nav-pill font-sans text-[14px] font-bold uppercase tracking-[0.12em]">
              {item.label}
            </button>
          ))}
        </div>
        <span className="font-sans text-[14px] font-medium text-neutral-600">{total} stories</span>
      </div>
      <HomeGrid items={items} loading={loading} />
    </div>
  );
}
