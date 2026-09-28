import { useState, useEffect, useRef, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { MagnifyingGlass, X, ClockCounterClockwise, Lightbulb } from '@phosphor-icons/react';
import client from '../../api/client';

interface Suggestion {
  title: string;
  article_id?: number;
}

interface SearchAutocompleteProps {
  query: string;
  onQueryChange: (q: string) => void;
  onSearch: (term: string) => void;
  placeholder?: string;
}

const SUGGEST_DEBOUNCE_MS = 300;
const HISTORY_KEY = 'fufu-search-history';
const MAX_SUGGESTIONS = 5;

function getHistory(): string[] {
  try { return JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]'); } catch { return []; }
}

function saveHistory(term: string) {
  const h = getHistory().filter((t) => t !== term);
  h.unshift(term);
  localStorage.setItem(HISTORY_KEY, JSON.stringify(h.slice(0, 10)));
}

export default function SearchAutocomplete({
  query,
  onQueryChange,
  onSearch,
  placeholder = '输入关键词搜索...',
}: SearchAutocompleteProps) {
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [suggestionsLoading, setSuggestionsLoading] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [history, setHistory] = useState<string[]>(getHistory());

  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLFormElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Fetch suggestions with debounce
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);

    if (!query.trim()) {
      setSuggestions([]);
      setSuggestionsLoading(false);
      setActiveIndex(-1);
      return;
    }

    setSuggestionsLoading(true);
    setActiveIndex(-1);

    debounceRef.current = setTimeout(async () => {
      try {
        const { data } = await client.get('/search/suggest', {
          params: { q: query.trim(), limit: MAX_SUGGESTIONS },
        });
        setSuggestions(data?.data ?? []);
      } catch {
        setSuggestions([]);
      } finally {
        setSuggestionsLoading(false);
      }
    }, SUGGEST_DEBOUNCE_MS);

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query]);

  // Click outside to close
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleFocus = useCallback(() => {
    setIsOpen(true);
    setHistory(getHistory());
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const typedTerm = query.trim();

    // If a suggestion is active, use that
    if (activeIndex >= 0 && activeIndex < suggestions.length) {
      onSearch(suggestions[activeIndex].title);
      saveHistory(suggestions[activeIndex].title);
      setHistory(getHistory());
      setIsOpen(false);
      return;
    }

    // If a history item is active
    const histIdx = activeIndex - suggestions.length;
    if (activeIndex >= suggestions.length && histIdx >= 0 && histIdx < history.length) {
      onSearch(history[histIdx]);
      saveHistory(history[histIdx]);
      setHistory(getHistory());
      setIsOpen(false);
      return;
    }

    // Fall back to typed query
    if (!typedTerm) return;
    onSearch(typedTerm);
    saveHistory(typedTerm);
    setHistory(getHistory());
    setIsOpen(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    const totalItems = suggestions.length + (suggestions.length === 0 ? history.length : 0);

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setActiveIndex((prev) => (prev + 1 >= totalItems ? 0 : prev + 1));
        break;
      case 'ArrowUp':
        e.preventDefault();
        setActiveIndex((prev) => (prev - 1 < 0 ? totalItems - 1 : prev - 1));
        break;
      case 'Escape':
        setIsOpen(false);
        setActiveIndex(-1);
        inputRef.current?.blur();
        break;
      case 'Enter':
        // Let form handle it via onSubmit
        break;
    }
  };

  const handleTermClick = (term: string) => {
    onSearch(term);
    saveHistory(term);
    setHistory(getHistory());
    setIsOpen(false);
  };

  const handleClear = () => {
    onQueryChange('');
    setSuggestions([]);
    setActiveIndex(-1);
    inputRef.current?.focus();
  };

  const showDropdown = isOpen && (suggestions.length > 0 || (!query.trim() && history.length > 0) || (query.trim() && suggestionsLoading));

  return (
    <form onSubmit={handleSubmit} className="relative mb-4" ref={containerRef}>
      <div className="relative">
        <MagnifyingGlass size={22} className="absolute left-5 top-1/2 -translate-y-1/2 text-fufu-text-muted z-10" />
        <input
          ref={inputRef}
          className="fufu-input pl-12 pr-12 text-lg rounded-fufu-input"
          value={query}
          onChange={(e) => { onQueryChange(e.target.value); if (!isOpen) setIsOpen(true); }}
          onFocus={handleFocus}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          autoComplete="off"
        />
        {query && (
          <button
            type="button"
            onClick={handleClear}
            className="absolute right-5 top-1/2 -translate-y-1/2 text-fufu-text-muted hover:text-fufu-pink transition-colors z-10"
          >
            <X size={18} />
          </button>
        )}
      </div>

      {/* Dropdown */}
      <AnimatePresence>
        {showDropdown && (
          <motion.div
            initial={{ opacity: 0, y: -8, scaleY: 0.95 }}
            animate={{ opacity: 1, y: 0, scaleY: 1 }}
            exit={{ opacity: 0, y: -8, scaleY: 0.95 }}
            transition={{ duration: 0.2, ease: 'easeOut' }}
            className="absolute left-0 right-0 top-full mt-1 z-50
                       bg-white rounded-fufu-card shadow-fufu-hover border border-fufu-teal/10
                       overflow-hidden"
          >
            {/* Loading skeleton */}
            {suggestionsLoading && (
              <div className="p-2 space-y-1.5">
                {Array.from({ length: 3 }).map((_, i) => (
                  <div key={i} className="flex items-center gap-3 px-3 py-2">
                    <div className="skeleton h-3 w-4 rounded" />
                    <div className="skeleton h-4 w-3/4 rounded" />
                  </div>
                ))}
              </div>
            )}

            {/* Suggestions */}
            {!suggestionsLoading && suggestions.length > 0 && (
              <div className="py-1">
                <div className="px-4 py-1.5">
                  <span className="font-cute text-[10px] text-fufu-text-muted flex items-center gap-1">
                    <Lightbulb size={12} /> 搜索建议
                  </span>
                </div>
                {suggestions.map((s, idx) => (
                  <button
                    key={s.article_id || s.title}
                    type="button"
                    onClick={() => handleTermClick(s.title)}
                    onMouseEnter={() => setActiveIndex(idx)}
                    className={`w-full text-left px-4 py-2 font-body text-sm flex items-center gap-3 transition-colors
                      ${activeIndex === idx
                        ? 'bg-fufu-teal/10 text-fufu-teal-deep'
                        : 'text-fufu-text hover:bg-fufu-cream'
                      }`}
                  >
                    <span className="text-fufu-text-muted text-xs">💡</span>
                    <span className="truncate">{s.title}</span>
                  </button>
                ))}
              </div>
            )}

            {/* History (when no suggestions or no query) */}
            {!suggestionsLoading && (!query.trim() || suggestions.length === 0) && history.length > 0 && (
              <div className="py-1">
                {suggestions.length > 0 && <div className="mx-4 border-t border-fufu-teal/5" />}
                <div className="px-4 py-1.5">
                  <span className="font-cute text-[10px] text-fufu-text-muted flex items-center gap-1">
                    <ClockCounterClockwise size={12} /> 搜索历史
                  </span>
                </div>
                {history.slice(0, 5).map((t, idx) => {
                  const histIdx = suggestions.length + idx;
                  return (
                    <button
                      key={t}
                      type="button"
                      onClick={() => handleTermClick(t)}
                      onMouseEnter={() => setActiveIndex(histIdx)}
                      className={`w-full text-left px-4 py-2 font-body text-sm flex items-center gap-3 transition-colors
                        ${activeIndex === histIdx
                          ? 'bg-fufu-teal/10 text-fufu-teal-deep'
                          : 'text-fufu-text hover:bg-fufu-cream'
                        }`}
                    >
                      <span className="text-fufu-text-muted text-xs">🕐</span>
                      <span className="truncate">{t}</span>
                    </button>
                  );
                })}
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </form>
  );
}
