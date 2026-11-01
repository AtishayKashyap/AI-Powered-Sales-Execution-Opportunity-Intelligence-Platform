import { useQuery } from "@tanstack/react-query";
import { BarChart3, Flame, ListTodo, Table2 } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "./api";
import { ExecutionPage } from "./pages/ExecutionPage";
import { OpportunitiesPage } from "./pages/OpportunitiesPage";
import { QueuePage } from "./pages/QueuePage";

const PAGES = {
  queue: { label: "Today's queue", icon: ListTodo, component: QueuePage },
  opportunities: { label: "Opportunities", icon: Table2, component: OpportunitiesPage },
  execution: { label: "Execution", icon: BarChart3, component: ExecutionPage },
} as const;
type PageKey = keyof typeof PAGES;

function pageFromHash(): PageKey {
  const key = window.location.hash.replace("#/", "");
  return key in PAGES ? (key as PageKey) : "queue";
}

export default function App() {
  const [page, setPage] = useState<PageKey>(pageFromHash);
  const health = useQuery({ queryKey: ["health"], queryFn: api.health, refetchInterval: 60_000, retry: 8 });

  useEffect(() => {
    const onHash = () => setPage(pageFromHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const Page = PAGES[page].component;
  return (
    <div className="shell">
      <nav className="sidebar" aria-label="Main">
        <div className="brand">
          <span className="brandMark">
            <Flame size={18} />
          </span>
          <span>
            <strong>SalesForge</strong>
            <small>Field execution</small>
          </span>
        </div>
        {(Object.keys(PAGES) as PageKey[]).map((key) => {
          const { label, icon: Icon } = PAGES[key];
          return (
            <a key={key} href={`#/${key}`} className={key === page ? "nav active" : "nav"} aria-current={key === page ? "page" : undefined}>
              <Icon size={16} /> {label}
            </a>
          );
        })}
        <div className={health.isSuccess ? "apiStatus live" : "apiStatus"}>
          <span />
          {health.isSuccess
            ? health.data.llm === "none"
              ? "API live · rule-based explanations"
              : `API live · ${health.data.llm}`
            : health.isError
              ? "API offline"
              : "Waking the API…"}
        </div>
      </nav>
      <main>
        <Page />
      </main>
    </div>
  );
}
