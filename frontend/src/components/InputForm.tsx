import { useState } from "react";
import type { UserInput } from "../api";

const INTEREST_OPTIONS = [
  "food",
  "music",
  "walks",
  "art",
  "coffee",
  "books",
  "movies",
  "nature",
  "shopping",
  "nightlife",
];

const CONSTRAINT_OPTIONS = [
  "vegetarian",
  "avoid crowded places",
  "quiet",
  "wheelchair accessible",
  "budget-conscious",
];

type Props = {
  loading: boolean;
  onSubmit: (input: UserInput) => void;
};

const underlineInput =
  "w-full bg-transparent border-0 border-b border-line-2 pb-2 pt-1 text-cream text-[15px] outline-none transition-colors duration-150 placeholder:text-faint focus:border-accent";

function FieldLabel({ children }: { children: React.ReactNode }) {
  return (
    <label className="block font-mono text-[10px] tracking-[0.25em] text-muted uppercase mb-2">
      {children}
    </label>
  );
}

export function InputForm({ loading, onSubmit }: Props) {
  const [city, setCity] = useState("Bangalore");
  const [budget, setBudget] = useState(2000);
  const [time, setTime] = useState("4 hours");
  const [mood, setMood] = useState("tired but wants to do something fun");
  const [interests, setInterests] = useState<string[]>(["food", "music", "walks"]);
  const [constraints, setConstraints] = useState<string[]>(["vegetarian", "avoid crowded places"]);

  const toggle = (list: string[], setter: (v: string[]) => void, val: string) => {
    setter(list.includes(val) ? list.filter((x) => x !== val) : [...list, val]);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit({ city, budget, available_time: time, mood, interests, constraints });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-7">

      <div>
        <FieldLabel>City</FieldLabel>
        <input
          className={underlineInput}
          value={city}
          onChange={(e) => setCity(e.target.value)}
          placeholder="Bangalore"
        />
      </div>

      <div>
        <FieldLabel>Budget (INR)</FieldLabel>
        <input
          className={underlineInput}
          type="number"
          value={budget}
          onChange={(e) => setBudget(Number(e.target.value))}
          min={0}
        />
      </div>

      <div>
        <FieldLabel>Available time</FieldLabel>
        <input
          className={underlineInput}
          value={time}
          onChange={(e) => setTime(e.target.value)}
          placeholder="e.g. 4 hours, half day"
        />
      </div>

      <div>
        <FieldLabel>Mood</FieldLabel>
        <textarea
          className={`${underlineInput} resize-none leading-relaxed`}
          rows={2}
          value={mood}
          onChange={(e) => setMood(e.target.value)}
          placeholder="How are you feeling? What kind of day do you want?"
        />
      </div>

      <div>
        <FieldLabel>Interests</FieldLabel>
        <div className="flex flex-wrap gap-1.5 mt-1">
          {INTEREST_OPTIONS.map((opt) => (
            <button
              key={opt}
              type="button"
              onClick={() => toggle(interests, setInterests, opt)}
              className={`px-2.5 py-1 font-mono text-[11px] tracking-[0.05em] border transition-colors duration-150 cursor-pointer ${
                interests.includes(opt)
                  ? "border-accent text-accent bg-accent-bg"
                  : "border-line-2 text-muted hover:border-muted hover:text-cream"
              }`}
            >
              {opt}
            </button>
          ))}
        </div>
      </div>

      <div>
        <FieldLabel>Constraints</FieldLabel>
        <div className="flex flex-wrap gap-1.5 mt-1">
          {CONSTRAINT_OPTIONS.map((opt) => (
            <button
              key={opt}
              type="button"
              onClick={() => toggle(constraints, setConstraints, opt)}
              className={`px-2.5 py-1 font-mono text-[11px] tracking-[0.05em] border transition-colors duration-150 cursor-pointer ${
                constraints.includes(opt)
                  ? "border-accent text-accent bg-accent-bg"
                  : "border-line-2 text-muted hover:border-muted hover:text-cream"
              }`}
            >
              {opt}
            </button>
          ))}
        </div>
      </div>

      <div className="pt-2">
        <button
          type="submit"
          disabled={loading}
          className="w-full bg-accent text-[#0c0a08] py-3.5 font-mono text-[12px] tracking-[0.2em] uppercase font-medium transition-colors duration-150 hover:bg-accent-bright disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? (
            <span className="flex items-center justify-center gap-2">
              <span
                className="inline-block w-3 h-3 border-2 border-[#0c0a08]/30 border-t-[#0c0a08] rounded-full"
                style={{ animation: "spin 0.7s linear infinite" }}
              />
              Planning...
            </span>
          ) : (
            "Plan my Saturday →"
          )}
        </button>
      </div>

    </form>
  );
}
