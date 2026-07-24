"""
Pure-Python polygon geometry helpers — no external dependencies.

Used by the zone creation endpoint to reject self-intersecting polygons
before they reach the database, where point-in-polygon algorithms (ray-casting,
winding number, PostGIS ST_Within) produce undefined results on bowtie shapes.
"""


def _ccw(ax: float, ay: float, bx: float, by: float, cx: float, cy: float) -> bool:
    """True if the turn A→B→C is strictly counter-clockwise."""
    return (cy - ay) * (bx - ax) > (by - ay) * (cx - ax)


def segments_cross(p1: list, p2: list, p3: list, p4: list) -> bool:
    """True if segment p1-p2 properly crosses segment p3-p4.

    Uses the CCW orientation test. Collinear overlap and shared endpoints
    return False — we only block segments that strictly pass through each
    other (the definition of a self-intersecting / bowtie polygon).
    """
    ax, ay = float(p1[0]), float(p1[1])
    bx, by = float(p2[0]), float(p2[1])
    cx, cy = float(p3[0]), float(p3[1])
    dx, dy = float(p4[0]), float(p4[1])
    return (
        _ccw(ax, ay, cx, cy, dx, dy) != _ccw(bx, by, cx, cy, dx, dy) and
        _ccw(ax, ay, bx, by, cx, cy) != _ccw(ax, ay, bx, by, dx, dy)
    )


def polygon_self_intersects(points: list) -> bool:
    """Return True if any two non-adjacent edges of the closed polygon cross.

    For n vertices the edges are i→(i+1)%n.
    Adjacent pairs share a vertex and are skipped:
      - edge i and edge i+1 share vertex i+1
      - edge 0 and edge n-1 share vertex 0
    Triangles (n=3) have no non-adjacent pairs and always return False.

    Known limit: only detects proper crossings (segments that pass through
    each other). A polygon that touches itself at a single shared coordinate
    without crossing — two loops joined at exactly one coincident vertex,
    forming a perfect "8" — is NOT detected. This case has near-zero
    probability when drawing with mouse/touch on a camera snapshot and
    is left as a known gap; it does not affect the bowtie / star cases
    that would corrupt point-in-polygon calculations.
    """
    n = len(points)
    if n < 4:
        return False
    for i in range(n):
        p1, p2 = points[i], points[(i + 1) % n]
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue  # edge 0 and edge n-1 share vertex 0
            p3, p4 = points[j], points[(j + 1) % n]
            if segments_cross(p1, p2, p3, p4):
                return True
    return False
