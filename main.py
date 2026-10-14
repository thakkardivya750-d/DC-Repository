import tkinter as tk
from tkinter import ttk, messagebox
from collections import deque

"""
Maekawa's Distributed Mutual Exclusion Algorithm — Tkinter simulator
Run: python main.py

This educational model demonstrates quorum-based voting:
- Each process requests permission from every member of its quorum.
- A voter grants at most one vote at a time; later requests wait in its queue.
- A process enters the critical section after receiving every vote in its quorum.
- On release, each voter gives its vote to the next waiting request.

This is a simplified teaching simulator. It demonstrates the core quorum/voting
idea and FIFO voter queues; it does not implement the full deadlock-recovery
messages (FAILED, INQUIRE, and YIELD) used in complete Maekawa variants.
"""

NODES = list(range(7))
QUORUMS = {
    0: {0, 1, 2},
    1: {1, 3, 4},
    2: {2, 3, 5},
    3: {0, 3, 6},
    4: {1, 5, 6},
    5: {2, 4, 6},
    6: {0, 4, 5},
}


class MaekawaSimulator:
    def __init__(self, root):
        self.root = root
        self.root.title("Maekawa Algorithm Simulator")
        self.root.geometry("1040x720")
        self.root.minsize(900, 620)
        self.root.configure(bg="#f3f6fb")

        self.voted_for = {}
        self.queues = {}
        self.requested = set()
        self.grants = {}
        self.in_cs = None
        self.history = []
        self._build_ui()
        self.reset(log=False)
        self.log("Welcome! Select a process and click Request Critical Section.")

    def _build_ui(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Treeview", rowheight=28, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))
        style.configure("TButton", font=("Segoe UI", 10), padding=7)
        style.configure("TCombobox", padding=5)

        header = tk.Frame(self.root, bg="#172554", padx=18, pady=14)
        header.pack(fill="x")
        tk.Label(header, text="MAEKAWA ALGORITHM SIMULATOR",
                 font=("Segoe UI", 18, "bold"), fg="white", bg="#172554").pack(anchor="w")
        tk.Label(header, text="Distributed mutual exclusion using quorum-based voting",
                 font=("Segoe UI", 10), fg="#cbd5e1", bg="#172554").pack(anchor="w", pady=(4, 0))

        controls = tk.Frame(self.root, bg="#f3f6fb", padx=16, pady=12)
        controls.pack(fill="x")
        tk.Label(controls, text="Process:", bg="#f3f6fb",
                 font=("Segoe UI", 10, "bold")).pack(side="left")
        self.process_var = tk.StringVar(value="P0")
        self.process_box = ttk.Combobox(controls, textvariable=self.process_var,
                                        values=[f"P{i}" for i in NODES],
                                        state="readonly", width=7)
        self.process_box.pack(side="left", padx=(8, 14))
        ttk.Button(controls, text="Request Critical Section",
                   command=self.request_cs).pack(side="left", padx=4)
        ttk.Button(controls, text="Release Critical Section",
                   command=self.release_cs).pack(side="left", padx=4)
        ttk.Button(controls, text="Reset", command=self.reset).pack(side="left", padx=4)

        self.status_var = tk.StringVar()
        status = tk.Label(self.root, textvariable=self.status_var, bg="#dbeafe",
                          fg="#1e3a8a", anchor="w", padx=14, pady=10,
                          font=("Segoe UI", 10, "bold"))
        status.pack(fill="x", padx=16, pady=(0, 10))

        body = tk.Frame(self.root, bg="#f3f6fb", padx=16)
        body.pack(fill="both", expand=True)

        left = tk.Frame(body, bg="white", padx=10, pady=10,
                        highlightbackground="#dbe2ea", highlightthickness=1)
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))
        tk.Label(left, text="Process Quorums", bg="white",
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0, 8))
        self.quorum_tree = ttk.Treeview(left, columns=("quorum", "state", "votes"),
                                        show="headings", height=8)
        for col, title, width in [
            ("quorum", "Quorum members", 170),
            ("state", "Process state", 140),
            ("votes", "Votes received", 100),
        ]:
            self.quorum_tree.heading(col, text=title)
            self.quorum_tree.column(col, width=width, anchor="center")
        self.quorum_tree.pack(fill="x")

        tk.Label(left, text="Voter Status", bg="white",
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(18, 8))
        self.voter_tree = ttk.Treeview(left, columns=("voter", "vote", "queue"),
                                       show="headings", height=8)
        for col, title, width in [
            ("voter", "Voter", 70),
            ("vote", "Vote currently held by", 160),
            ("queue", "Waiting queue (FIFO)", 210),
        ]:
            self.voter_tree.heading(col, text=title)
            self.voter_tree.column(col, width=width, anchor="center")
        self.voter_tree.pack(fill="both", expand=True)

        right = tk.Frame(body, bg="white", padx=10, pady=10,
                         highlightbackground="#dbe2ea", highlightthickness=1)
        right.pack(side="right", fill="both", expand=True, padx=(8, 0))
        tk.Label(right, text="Activity Log", bg="white",
                 font=("Segoe UI", 12, "bold")).pack(anchor="w")
        self.log_box = tk.Text(right, wrap="word", height=20, state="disabled",
                               font=("Consolas", 9), bg="#f8fafc",
                               relief="flat", padx=8, pady=8)
        self.log_box.pack(fill="both", expand=True, pady=(8, 0))
        self.log_box.tag_configure("success", foreground="#15803d")
        self.log_box.tag_configure("warn", foreground="#b45309")
        self.log_box.tag_configure("info", foreground="#1d4ed8")

        footer = tk.Label(
            self.root,
            text="Rule: a process enters the critical section only after receiving votes from every member of its quorum.",
            bg="#f3f6fb", fg="#475569", font=("Segoe UI", 9), padx=16, pady=10
        )
        footer.pack(fill="x")

    def selected_node(self):
        return int(self.process_var.get()[1:])

    def reset(self, log=True):
        self.voted_for = {p: None for p in NODES}
        self.queues = {p: deque() for p in NODES}
        self.requested = set()
        self.grants = {p: set() for p in NODES}
        self.in_cs = None
        if hasattr(self, "log_box"):
            self._clear_log()
        self.refresh()
        if log:
            self.log("Simulation reset. All voters are free and all queues are empty.")

    def request_cs(self):
        p = self.selected_node()
        if p in self.requested:
            self.log(f"P{p} has already requested the critical section.", "warn")
            return
        if self.in_cs is not None:
            self.log(f"P{self.in_cs} is currently in the critical section. P{p}'s request is queued at voters.", "warn")
        self.requested.add(p)
        self.grants[p] = set()
        quorum = sorted(QUORUMS[p])
        self.log(f"P{p} broadcasts REQUEST to quorum {self.fmt_set(quorum)}.", "info")
        for voter in quorum:
            self._ask_vote(p, voter)
        self._check_entry(p)
        self.refresh()

    def _ask_vote(self, requester, voter):
        if self.voted_for[voter] is None:
            self.voted_for[voter] = requester
            self.grants[requester].add(voter)
            self.log(f"Voter P{voter} GRANTS its vote to P{requester}.")
        elif self.voted_for[voter] == requester:
            self.grants[requester].add(voter)
        else:
            if requester not in self.queues[voter]:
                self.queues[voter].append(requester)
            self.log(f"Voter P{voter} is voting for P{self.voted_for[voter]}; P{requester} waits in its FIFO queue.", "warn")

    def _check_entry(self, p):
        if p not in self.requested:
            return
        if self.grants[p] >= QUORUMS[p] and self.in_cs is None:
            self.in_cs = p
            self.log(f"SUCCESS: P{p} received all {len(QUORUMS[p])} quorum votes and ENTERED the critical section.", "success")
        elif self.grants[p] >= QUORUMS[p] and self.in_cs is not None and self.in_cs != p:
            self.log(f"P{p} has all quorum votes but waits for P{self.in_cs} to leave the critical section.", "warn")

    def release_cs(self):
        p = self.selected_node()
        if p not in self.requested:
            self.log(f"P{p} has no active request to release.", "warn")
            return
        if self.in_cs == p:
            self.log(f"P{p} RELEASES the critical section.", "success")
            self.in_cs = None
        else:
            self.log(f"P{p} cancels its pending request.", "warn")

        # Remove this request from all voter queues, then release any votes it held.
        for voter in NODES:
            if p in self.queues[voter]:
                self.queues[voter] = deque(x for x in self.queues[voter] if x != p)
        for voter in sorted(QUORUMS[p]):
            if self.voted_for[voter] == p:
                self.voted_for[voter] = None
                self.grants[p].discard(voter)
                self.log(f"Voter P{voter} releases its vote.")
                self._grant_next(voter)
        self.requested.discard(p)
        self.grants[p] = set()
        self._reevaluate()
        self.refresh()

    def _grant_next(self, voter):
        while self.queues[voter]:
            next_p = self.queues[voter].popleft()
            if next_p in self.requested and voter in QUORUMS[next_p]:
                self.voted_for[voter] = next_p
                self.grants[next_p].add(voter)
                self.log(f"Voter P{voter} grants its released vote to waiting P{next_p}.")
                self._check_entry(next_p)
                break

    def _reevaluate(self):
        # If a process already has all votes, allow it to enter once the CS is free.
        if self.in_cs is None:
            ready = [p for p in self.requested if self.grants[p] >= QUORUMS[p]]
            if ready:
                p = min(ready)
                self.in_cs = p
                self.log(f"P{p} ENTERED the critical section after it became free.", "success")

    @staticmethod
    def fmt_set(values):
        return "{" + ", ".join(f"P{x}" for x in values) + "}"

    def log(self, message, tag=""):
        self.log_box.configure(state="normal")
        prefix = f"{len(self.history) + 1:03d}  "
        self.log_box.insert("end", prefix + message + "\n", tag)
        self.log_box.see("end")
        self.log_box.configure(state="disabled")
        self.history.append(message)
        self.refresh_status()

    def _clear_log(self):
        self.history = []
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    def refresh_status(self):
        if self.in_cs is not None:
            self.status_var.set(f"CRITICAL SECTION: P{self.in_cs} is inside")
        else:
            active = sorted(self.requested)
            self.status_var.set(
                "CRITICAL SECTION: FREE" +
                (f"   |   Active requests: {self.fmt_set(active)}" if active else "   |   No active requests")
            )

    def refresh(self):
        if not hasattr(self, "quorum_tree"):
            return
        for item in self.quorum_tree.get_children():
            self.quorum_tree.delete(item)
        for p in NODES:
            state = "IN CRITICAL SECTION" if self.in_cs == p else (
                "Requesting" if p in self.requested else "Idle"
            )
            self.quorum_tree.insert("", "end", iid=f"q{p}", values=(
                f"{self.fmt_set(sorted(QUORUMS[p]))}",
                state,
                f"{len(self.grants[p])}/{len(QUORUMS[p])}"
            ))
        for item in self.voter_tree.get_children():
            self.voter_tree.delete(item)
        for p in NODES:
            vote = f"P{self.voted_for[p]}" if self.voted_for[p] is not None else "FREE"
            queue = ", ".join(f"P{x}" for x in self.queues[p]) or "—"
            self.voter_tree.insert("", "end", iid=f"v{p}", values=(f"P{p}", vote, queue))
        self.refresh_status()


def main():
    root = tk.Tk()
    MaekawaSimulator(root)
    root.mainloop()


if __name__ == "__main__":
    main()
