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

export function InputForm({ loading, onSubmit }: Props) {
  const [city, setCity] = useState("Bangalore");
  const [budget, setBudget] = useState(2000);
  const [time, setTime] = useState("4 hours");
  const [mood, setMood] = useState("tired but wants to do something fun");
  const [interests, setInterests] = useState<string[]>(["food", "music", "walks"]);
  const [constraints, setConstraints] = useState<string[]>(["vegetarian", "avoid crowded places"]);

  const toggle = (
    list: string[],
    setter: (v: string[]) => void,
    val: string
  ) => {
    setter(list.includes(val) ? list.filter((x) => x !== val) : [...list, val]);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit({
      city,
      budget,
      available_time: time,
      mood,
      interests,
      constraints,
    });
  };

  return (
    <form className="panel" onSubmit={handleSubmit}>
      <div className="field">
        <label>City</label>
        <input value={city} onChange={(e) => setCity(e.target.value)} placeholder="Bangalore" />
      </div>

      <div className="field">
        <label>Budget (INR)</label>
        <input
          type="number"
          value={budget}
          onChange={(e) => setBudget(Number(e.target.value))}
          min={0}
        />
      </div>

      <div className="field">
        <label>Available time</label>
        <input
          value={time}
          onChange={(e) => setTime(e.target.value)}
          placeholder="e.g. 4 hours, half day"
        />
      </div>

      <div className="field">
        <label>Mood</label>
        <textarea
          rows={2}
          value={mood}
          onChange={(e) => setMood(e.target.value)}
          placeholder="How are you feeling? What kind of day do you want?"
        />
      </div>

      <div className="field">
        <label>Interests</label>
        <div className="chips">
          {INTEREST_OPTIONS.map((opt) => (
            <span
              key={opt}
              className={`chip ${interests.includes(opt) ? "active" : ""}`}
              onClick={() => toggle(interests, setInterests, opt)}
            >
              {opt}
            </span>
          ))}
        </div>
      </div>

      <div className="field">
        <label>Constraints</label>
        <div className="chips">
          {CONSTRAINT_OPTIONS.map((opt) => (
            <span
              key={opt}
              className={`chip ${constraints.includes(opt) ? "active" : ""}`}
              onClick={() => toggle(constraints, setConstraints, opt)}
            >
              {opt}
            </span>
          ))}
        </div>
      </div>

      <button className="btn" type="submit" disabled={loading}>
        {loading ? (
          <>
            <span className="spinner" /> Planning your Saturday...
          </>
        ) : (
          "Plan my Saturday"
        )}
      </button>
    </form>
  );
}
