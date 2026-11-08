# ARC DSL reference (for writing programs)

You see the train pairs of one ARC task. Write a JSON program mapping every train input exactly to its output; it is checked on train, scored on test.

## Answer format

Return one block: `{"kind":"transform","in":"grid","out":"grid","body":PROGRAM}`.
PROGRAM is a list of steps `[name, *params]` applied left to right: each step maps one grid to one grid.
Other kinds are `{"kind":"pred","in":"object","out":"bool","body":AST}`, `{"kind":"extract","in":"grid","out":"json","body":BODY}` and `{"kind":"formula","in":"features","out":"int","body":BODY}`. A pred or formula block alone produces no grid and is only syntax-checked. An extract block whose prop is `subgrid` or `object` runs as `[["crop_extract",BODY]]`. Use `transform` and put sub-rules **inline** as parameters.

Grids are lists of rows of ints 0-9. Every intermediate grid must be 1..30 x 1..30. The final grid must contain only 0-9.
**Color 10 = MARK**, an internal marker that some primitives emit. A later `colormap` (or `local_rule`) must turn it into 0-9, or the program fails.
Any exception (an ambiguous selector, a bad parameter, an undefined value) fails that pair.

**Background (bg).** Object code uses the task bg = the most frequent color over all train inputs and outputs (ties: commonest border color, then 0); a grid where that color covers <40% of cells falls back to its own most frequent color. Some primitives (`crop_bbox`, `fill_enclosed`, cell primitives, `recolor_extract`/`keep_extract`, extract prop `object`) always use the current grid's own most frequent color. `split_overlay` uses bg = 0 if the grid contains any 0.

## Objects

`conn` is one of `"4same"` `"8same"` `"4multi"` `"8multi"`. The digit is the connectivity (4 or 8 neighbours). `same` means one color per object; `multi` means any non-bg colors join.

Object attributes (`attr`): every value is an int or a str.
- `color`: the majority color.
- `size`: the cell count.
- `size_rank`: 1 = largest distinct size, 2 = next.
- `is_largest`, `is_smallest`: 0 or 1; ties all count.
- `touches_border`, `has_hole`: 0 or 1. A hole is a non-object cell inside the bbox that the outside cannot reach by 4-steps.
- `h`, `w`: the bbox height and width.
- `shape`: the str `"HxW:bits"`, with row-major bits of the bbox, e.g. `"2x2:1110"`.
- `color_count`: how many objects share this object's color.
- `shape_count`: how many objects share its shape.

**Selector** = three params `conn, attr, value`. `attr` is one of the attributes above (test `attr == value`), or `"all"` (value ignored, write 1), or `"pred"` (value = an inline predicate AST).

**Predicate AST** (inline value of `"pred"`):
- `["eq"|"ne"|"gt"|"lt", attr, v]`: `gt` and `lt` hold only on ints. An unknown attr compares as null, so it is false.
- `["rank", attr, "max"|"min"]`: the object has the extreme value of attr among all objects.
- `["and", p, ...]`, `["or", p, ...]`, `["not", p]`.

Do not wrap the AST in a `{"kind":"pred"}` dict here: that is rejected.

## Grid-scope extract body `[prop, sel]`

`sel` forms:
- `["largest"|"smallest", conn]`: the unique max/min size object. A tie is an error.
- `["unique_color", conn]`: the only object whose color occurs once.
- `["unique_shape", conn]`: the only object whose shape occurs once.
- `["all", conn]`.
- `["color", conn, c]`: objects of color c.
- `["pred", conn, AST]`.

`prop` (computed over the union of the selected objects):
- `bbox`: `[top, left, h, w]`.
- `color`: must be the one color they share.
- `size`: cells.
- `count`: objects (0 is allowed).
- `cells`: `[[y,x],...]`.
- `subgrid`: the bbox crop.
- `object`: the crop with unselected cells set to bg.

An empty selection is an error except for `count`.
Where an extract is a parameter you may pass the bare body or the shell `{"kind":"extract","body":...}`.

## Object-scope extract body

Shape: `{"scope":"object","sel":[op, conn],"prop":p}`. It is evaluated for each selected anchor object.

`op`:
- `this`: the anchor itself.
- `nearest`, `nearest_same_color`, `nearest_other_color`: the unique closest other object, by bbox gap.
- `nearest_aligned`, `nearest_aligned_same_color`, `nearest_aligned_other_color`: the same, restricted to objects sharing rows or columns with the anchor.
- `touching`: all other objects 8-adjacent to the anchor.
- `largest`: the grid's unique largest object.

`p`:
- `color`: one shared color.
- `size`, `size_rank`.
- `dir_to`: `"up"|"down"|"left"|"right"` toward the single selected object. They must be aligned. Not allowed with `this`.
- `dist_to`: the background gap to that object. Not allowed with `this`.
- `wall_dir`: the direction of the anchor's nearest border. Only allowed with `this`, and must be unique.

If the value is undefined for an anchor, that object is left unchanged. The `{"kind":"extract","body":{...}}` shell is accepted too.

## Formula body (int from features of the current grid)

- `["lin",x,a,b]` = a·x+b, with a in 1..4 and b in -3..3.
- `["mul",x,y]`, `["max",x,y]`, `["min",x,y]`.
- `["sq",x]`.
- `["div",x,k]` = x/k, which must divide exactly; k in 2..5.
- `["const",k]`.
- `["lin2",x,a,y,b]` = a·x+b·y, with a in {1,2,3,-1} and b in {-2,-1,1,2}.
- `["mulc",x,c,y]` = (x+c)·y, with c in {-2,-1,1,2}.

Values outside these ranges are rejected. The result must be in 1..30. Pass the bare list only: a `{"kind":"formula"}` dict is rejected.

Feature names x, y (bg as above):
- `h`, `w`.
- `n_color`: distinct non-bg colors.
- `n_fg`: non-bg cells.
- `n_bg`: bg cells.
- `n_obj`: 4same objects.
- `n_obj8`: 8multi objects.
- `n_shape`: distinct 4same shapes.
- `max_obj_h`, `max_obj_w`, `min_obj_h`, `min_obj_w`, `max_obj_size`, `min_obj_size`: over 4same objects.
- `cnt_0` .. `cnt_9`: cells of each color.

## Primitives

### Geometry (no params)

`flip_lr`, `flip_ud`, `transpose`, `rot90` (clockwise), `rot180`, `rot270`, `anti_transpose`.

### Scaling and tiling

- `["upscale",fy,fx]`: each cell becomes an fy×fx block.
- `["tile",ny,nx]`: repeat the whole grid ny×nx times.
- `["downscale",fy,fx]`: keep the top-left cell of each fy×fx block. fy and fx must divide the grid.
- `["upscale_n",F,F]`, `["tile_n",F,F]`: the same, with formula factors.
- `["mirror_tile","lr"|"ud"|"quad"]`: append the mirror to the right, below, or both (2×2).
- `["self_tile","pos"|"neg"]`: output is (h·h)×(w·w). A copy of the grid goes at every non-bg cell (`pos`) or bg cell (`neg`); the rest is bg.

### Crop and resize

- `["crop_bbox"]`: crop to the bbox of the non-bg cells.
- `["crop_object",conn,how]`: crop the bbox of one object.
  - `conn` is effectively `"4same"` or `"8multi"`; other values act as 4-connected multi-color.
  - `how` is one of:
    - `largest`, `smallest`: ties take the first object in row-major order.
    - `top_left`: the first object in row-major order.
    - `most_colors`.
    - `unique_color`: the only single-color object whose color is unique.
- `["resize_crop",F_h,F_w]`: crop, or pad with bg, from the top-left corner.
- `["canvas",F_h,F_w,col]`: a new single-color grid. `col` is 0-9, `"fg"` (the most frequent non-bg color) or `"bg"`.

### Overlay halves

`["split_overlay",axis,op]`: `axis` `"h"` splits top/bottom; `"v"` splits left/right. With an odd length, the middle line must be one color and is dropped.
Each output cell is MARK if `op(A≠bg, B≠bg)`, else 0, where A is the top/left half.
`op` is one of `and`, `or`, `xor`, `nor`, or `left` (A and not B).

### Fill

- `["fill_enclosed"]`: bg cells that cannot 4-reach the border through bg become MARK.
- `["fill_holes",c]`: bg cells inside the holes of any single 8multi object become c.
- `["symmetrize",mode,hole]`: every cell of color `hole` takes the value of its mirror image(s), choosing the first image that is not `hole`. `mode` is one of:
  - `lr`, `ud`.
  - `both`: lr, ud, rot180.
  - `transpose`.
  - `rot`: rot90, rot180, rot270.

  `transpose` and `rot` need a square grid.

### Gravity

`["gravity","down"|"up"|"left"|"right"]`: per column or row, non-bg *cells* slide to that side, keeping their order.

### Separator-grid cells

These need full lines of one color that cut the board into ≥2 equal cells (an outer frame is allowed). The cell bg is the majority color inside the cells.
- `["pick_cell",how]`: return one cell. `how` is one of:
  - `unique`: the only cell whose content occurs once.
  - `unique_mask`: the same, comparing only which pixels are non-bg.
  - `most_colors`, `least_colors`, `most_pixels`, `least_pixels`: the extreme must be unique.
  - `has_color`: written `["pick_cell","has_color",c]`; the only cell containing c.
- `["overlay_cells",op]`: output is cell-sized.
  - `and` (all cells non-bg), `or`, `xor` (exactly one), `nor`: MARK or 0.
  - `stack`, `stack_rev`: the first non-bg value in cell order (or reversed order); colors are kept.
- `["cells_to_pixels",mode]`: one pixel per cell. `mode` is one of:
  - `majority`: the commonest non-bg color, else bg.
  - `any`: MARK if the cell has content, else 0.
  - `uniform`: the color if the cell is entirely one non-bg color, else bg.
  - `max_pixels`: MARK on the cell(s) with the most pixels, else 0.
- `["fill_cells",mode]`: same size as the input; each cell is painted with that summary and separators are kept.

### Object actions (same-size)

These take a selector `conn,attr,value`.
- `["recolor_sel",conn,attr,value,c]`.
- `["delete_sel",conn,attr,value]`: the selected objects become bg.
- `["keep_sel",conn,attr,value]`: all other objects become bg.
- `["move_sel",conn,attr,value,dir]`: slide each selected object until it would leave the grid or hit a non-bg cell.
- `["extend_sel",conn,attr,value,dir]`: from each object, rays in `dir` in each cell's own color, over bg, until a non-bg cell or the border.

### Per-object rules

Parameters are `conn,attr,value,SRC`, where SRC is an object-scope extract.
- `["recolor_from",...]`: SRC must give a color 0-9.
- `["move_from",...]`, `["extend_from",...]`: SRC must give a direction.

### Extract-driven

E is a grid-scope extract.
- `["crop_extract",E]`: E's prop must be `subgrid` or `object`.
- `["fill_extract",E]`: the whole grid becomes the color E gives.
- `["recolor_extract",E]`: every non-bg cell becomes E's color.
- `["keep_extract",E]`: only E's selector is used. Cells outside the selected objects become bg.
- `["paint_count",E_n,col,mode]`: a row (1×n), col (n×1) or square (n×n) of `col`. `mode` is `"row"`, `"col"` or `"square"`. `col` is an int or a color extract; n is 1..30.

### Special steps

- `["colormap",[[src,dst],...]]`: recolor cells. Colors not listed stay. This is the way to resolve MARK (10).
- `["object_colormap",[conn,attr,[[key,c],...]]]`: each object whose `attr` value is a listed key gets color c. Unlisted keys and c = -1 keep the object. The split form `[conn,attr,[[v,c]],other]` gives `attr==v` → c and every other object → `other`. `attr` is from the attribute list, not `pred` or `all`.
- `["local_rule","n4"|"n8",[[center,n1,..,nk,out],...]]`: a cell whose center and neighbour key matches a row becomes `out`.
  - The n4 neighbour order is up, down, left, right. The n8 order is NW, N, NE, W, E, SW, S, SE.
  - -1 means outside the grid.
  - An unmatched key keeps the cell, but an unmatched MARK cell is an error.

Names like `pred_*`, `extract_*`, `formula_*` and `m_*` are the repo's own blocks. Don't invent them; write bodies inline.

## Verified examples (all train and test pairs pass)

1. 0520fde7: two 3×3 halves split by a column; cells set in both → 2.
   `[["split_overlay","v","and"],["colormap",[[10,2]]]]`
2. 7b6016b9: inside of closed loops → 2, outside bg → 3.
   `[["fill_enclosed"],["colormap",[[0,3],[10,2]]]]`
3. 0b148d64: crop the quadrant whose color is rare.
   `[["crop_extract",["subgrid",["pred","4same",["and",["lt","shape_count",3],["rank","color_count","min"]]]]]]`
4. 445eab21: output 2×2 in the color of the widest object.
   `[["fill_extract",["color",["pred","8same",["and",["ne","color",0],["rank","w","max"]]]]],["downscale",5,5]]`
5. ac0a08a4: upscale by the number of colors.
   `[["upscale_n",["lin","n_color",1,0],["lin","n_color",1,0]]]`
6. d2abd087: objects of size 6 → 2, all others → 1.
   `[["object_colormap",["4same","size",[[6,2]],1]]]`
7. 810b9b61: color-1 shapes with a hole → 3.
   `[["recolor_sel","4same","pred",["and",["eq","color",1],["eq","has_hole",1]],3]]`
8. 2204b7a8: each 3-dot takes the color of the nearest other-colored object.
   `[["recolor_from","4same","color",3,{"scope":"object","sel":["nearest_other_color","8same"],"prop":"color"}]]`
9. d43fd935: every object shoots a ray toward the big block when aligned with it.
   `[["extend_from","4same","all",1,{"scope":"object","sel":["largest","4same"],"prop":"dir_to"}]]`
10. 05f2a901: the color-2 shape slides toward the aligned object until it touches.
    `[["move_from","4same","color",2,{"scope":"object","sel":["nearest_aligned","4same"],"prop":"dir_to"}]]`
11. 54d9e175: each separator cell is filled by its majority color, then colors are mapped.
    `[["fill_cells","majority"],["colormap",[[1,6],[2,7],[3,8],[4,9]]]]`
12. 3618c87e: a local neighbourhood table.
    `[["local_rule","n4",[[1,0,5,0,-1,0],[1,0,5,0,0,0],[5,5,-1,5,-1,1],[5,5,-1,5,5,1]]]]`

## Limits (say "not expressible" rather than forcing a fit)

The DSL cannot express:
- Drawing lines or shapes between two given points or objects, or diagonal rays. `extend_*` only goes up/down/left/right to the first obstacle.
- Translating or copying an object by a fixed offset, stamping a pattern at markers, or rotating or flipping one object in place. Geometry is whole-grid only.
- Cropping at explicit coordinates; `resize_crop` is top-left only.
- Assembling several objects into a new layout; sorting or arranging objects.
- Pattern or sequence continuation; periodic repair, except mirror symmetry via `symmetrize`.
- Arithmetic on colors, or conditionals and loops. Per-object choice is limited to the selectors, object_colormap and the object-scope sources above.
- Counting beyond `paint_count`, the formulas and the tables.
- Output colors that depend on a key never seen in train. colormap passes unseen colors through unchanged.
- Dense grids whose true background is not the majority color, because bg is per-grid majority.

Memorized fits (huge `local_rule`/`colormap` tables) likely fail test; prefer the shortest general rule.
