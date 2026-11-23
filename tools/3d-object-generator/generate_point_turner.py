import math

def write_stl(triangles, filename):
    """Writes a list of triangles to an ASCII STL file."""
    with open(filename, 'w') as f:
        f.write(f"solid returned_coin\n")
        for tri in triangles:
            # Calculate normal (simplified, doesn't affect printing usually, but good practice)
            # For this script, we'll use 0 0 0 as slicers usually recalculate normals
            f.write("  facet normal 0 0 0\n")
            f.write("    outer loop\n")
            for vertex in tri:
                f.write(f"      vertex {vertex[0]:.6f} {vertex[1]:.6f} {vertex[2]:.6f}\n")
            f.write("    endloop\n")
            f.write("  endfacet\n")
        f.write("endsolid returned_coin\n")

def get_profile(y, total_length):
    """
    Defines the width (x) and thickness (z) based on the length position (y).
    Returns (width_radius, thickness_radius)
    """
    # Parameters
    handle_width = 20.0
    handle_thickness = 4.0
    tip_width = 2.0
    tip_thickness = 1.0
    
    # Tapering logic
    # From 0 to 70% length: Handle (slight taper)
    # From 70% to 100% length: Tip (sharp taper)
    
    ratio = y / total_length
    
    if ratio < 0.7:
        # Handle section
        w = handle_width - (handle_width - (handle_width * 0.8)) * (ratio / 0.7)
        t = handle_thickness
    else:
        # Point section
        sub_ratio = (ratio - 0.7) / 0.3
        start_w = handle_width * 0.8
        w = start_w - (start_w - tip_width) * sub_ratio
        t = handle_thickness - (handle_thickness - tip_thickness) * sub_ratio
        
    return w / 2, t / 2

def generate_geometry():
    length = 140.0
    steps = 50
    triangles = []
    
    # We generate rings of vertices along the Y axis
    rings = []
    
    for i in range(steps + 1):
        y = (i / steps) * length
        xr, zr = get_profile(y, length)
        
        # Create an elliptical cross section with 16 points
        # We use an ellipse to ensure smooth edges (friendly to fabric)
        ring_segments = 16
        ring = []
        for j in range(ring_segments):
            angle = (j / ring_segments) * 2 * math.pi
            x = xr * math.cos(angle)
            z = zr * math.sin(angle)
            ring.append((x, y, z))
        rings.append(ring)
        
    # Connect rings with triangles
    for i in range(len(rings) - 1):
        current_ring = rings[i]
        next_ring = rings[i+1]
        count = len(current_ring)
        
        for j in range(count):
            p1 = current_ring[j]
            p2 = current_ring[(j + 1) % count]
            p3 = next_ring[(j + 1) % count]
            p4 = next_ring[j]
            
            # Triangle 1
            triangles.append([p1, p2, p4])
            # Triangle 2
            triangles.append([p2, p3, p4])
            
    # Cap the bottom (Handle end)
    bottom_ring = rings[0]
    center_bottom = (0, 0, 0)
    for j in range(len(bottom_ring)):
        p1 = bottom_ring[j]
        p2 = bottom_ring[(j + 1) % len(bottom_ring)]
        # Order for normal pointing out
        triangles.append([center_bottom, p2, p1])
        
    # Cap the top (Tip end)
    top_ring = rings[-1]
    center_top = (0, length, 0)
    for j in range(len(top_ring)):
        p1 = top_ring[j]
        p2 = top_ring[(j + 1) % len(top_ring)]
        triangles.append([center_top, p1, p2])

    return triangles

if __name__ == "__main__":
    try:
        tris = generate_geometry()
        output_filename = "retourne_coin.stl"
        write_stl(tris, output_filename)
        print(f"Success: Generated {output_filename} with {len(tris)} triangles.")
    except Exception as e:
        print(f"Error: {e}")
