import heapq
import random

class FarmMap:
    def __init__(self, size=100):
        self.size = size
        self.plants = {}  # (x, y) -> crop_emoji
        self.tags = {}    # tag_id -> (x, y)
        self.blocked = set()
        self._build_grid()

    def _build_grid(self):
        crop_palette = ['🌽', '🍅', '🥬', '🥕', '🍓', '🍆', '🥦', '🌶️']

        # Ensure base station origin area remains open
        for bx in range(4):
            for by in range(4):
                self.blocked.discard((bx, by))

        # Adjacent row blocks
        row_y_groups = [
            (16, 17),
            (36, 37),
            (56, 57),
            (76, 77)
        ]

        # Shared vertical corridors (5-cells wide)
        corridor_centers = [15, 40, 65, 88]
        corridor_cells = set()
        for cc in corridor_centers:
            for dx in range(-2, 3):
                corridor_cells.add(cc + dx)

        for y1, y2 in row_y_groups:
            c1 = random.choice(crop_palette)
            c2 = random.choice(crop_palette)
            for x in range(self.size):
                if x not in corridor_cells:
                    self.plants[(x, y1)] = c1
                    self.blocked.add((x, y1))
                    self.plants[(x, y2)] = c2
                    self.blocked.add((x, y2))

        # Exactly 8 AprilTags balanced across the 100x100 grid quadrants & aisles
        candidate_8_tags = [
            (25, 8),    # Tag 1: South-West
            (75, 8),    # Tag 2: South-East
            (20, 27),   # Tag 3: Mid-South-West
            (80, 27),   # Tag 4: Mid-South-East
            (50, 47),   # Tag 5: Central Field
            (20, 67),   # Tag 6: Mid-North-West
            (80, 67),   # Tag 7: Mid-North-East
            (50, 88),   # Tag 8: North-Center
        ]

        for tid, (tx, ty) in enumerate(candidate_8_tags, start=1):
            while (tx, ty) in self.blocked:
                ty += 1
            self.tags[tid] = (tx, ty)

    def neighbors(self, node):
        x, y = node
        candidates = [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
        valid = []
        for nx, ny in candidates:
            if 0 <= nx < self.size and 0 <= ny < self.size:
                if (nx, ny) not in self.blocked:
                    valid.append((nx, ny))
        return valid

    def astar(self, start, goal):
        if start == goal:
            return [start]

        frontier = []
        heapq.heappush(frontier, (0, start))
        came_from = {start: None}
        cost_so_far = {start: 0}

        while frontier:
            _, curr = heapq.heappop(frontier)

            if curr == goal:
                break

            for nxt in self.neighbors(curr):
                new_cost = cost_so_far[curr] + 1
                if nxt not in cost_so_far or new_cost < cost_so_far[nxt]:
                    cost_so_far[nxt] = new_cost
                    priority = new_cost + abs(goal[0] - nxt[0]) + abs(goal[1] - nxt[1])
                    heapq.heappush(frontier, (priority, nxt))
                    came_from[nxt] = curr

        if goal not in came_from:
            return []

        path = []
        c = goal
        while c:
            path.append(c)
            c = came_from[c]
        path.reverse()
        return path
