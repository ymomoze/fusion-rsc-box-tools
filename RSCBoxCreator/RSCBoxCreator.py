# RSCBoxCreator.py
# Fusion 360 Add-in
# A式箱 / RSC箱を作成するためのアドイン

import adsk.core
import adsk.fusion
import traceback


_app = None
_ui = None
_handlers = []


# =========================
# 01.アドイン設定
# =========================

ADDIN_NAME = 'RSCBoxCreator'
PANEL_ID = 'SolidCreatePanel'
COMMAND_ID = 'RSCBoxCreator_CreateBox'
COMMAND_NAME = 'A式箱を作成'
COMMAND_DESCRIPTION = '内寸を入力してA式箱を作成します。'


# =========================
# 02.入力値の読み取り
# =========================

def parse_box_size(text):
    """
    入力例:
    400,250,100,5

    戻り値:
    length, width, height, thickness
    """
    parts = text.replace('，', ',').split(',')

    if len(parts) != 4:
        raise ValueError('入力は「長さ,幅,高さ,厚み」の4つにしてください。')

    values = []
    for part in parts:
        value = float(part.strip())
        if value <= 0:
            raise ValueError('すべて0より大きい数値にしてください。')
        values.append(value)

    return values[0], values[1], values[2], values[3]

def calc_outer_size(inner_width, inner_depth, inner_height, thickness):
    outer_width = inner_width + thickness * 2
    outer_depth = inner_depth + thickness * 2
    outer_height = inner_height + thickness * 4

    return outer_width, outer_depth, outer_height

# =========================
# 03. 箱作成処理
# =========================

# -------------------------
# 03-1. 親箱コンポーネント作成
# -------------------------

def check_hybrid_design():
    design = adsk.fusion.Design.cast(_app.activeProduct)

    if design is None:
        raise ValueError(
            'A式箱はハイブリッドデザインで作成してください。\n'
            '新規作成時に「ハイブリッドデザイン」を選択してから実行してください。'
        )

    root_comp = design.rootComponent

    if root_comp is None:
        raise ValueError(
            'A式箱はハイブリッドデザインで作成してください。\n'
            '新規作成時に「ハイブリッドデザイン」を選択してから実行してください。'
        )

    # パーツデザインでは新規コンポーネントを追加できないため、
    # 入力画面を出す前に、仮コンポーネントを作成できるか確認します。
    try:
        transform = adsk.core.Matrix3D.create()
        test_occ = root_comp.occurrences.addNewComponent(transform)
        test_occ.deleteMe()

    except:
        raise ValueError(
            'A式箱はハイブリッドデザインで作成してください。\n'
            '新規作成時に「ハイブリッドデザイン」を選択してから実行してください。'
        )

def create_box_component():
    design = adsk.fusion.Design.cast(_app.activeProduct)

    if design is None:
        raise ValueError(
            'A式箱はハイブリッドデザインで作成してください。\n'
            '新規作成時に「ハイブリッドデザイン」を選択してから実行してください。'
        )

    root_comp = design.rootComponent

    if root_comp is None:
        raise ValueError(
            'A式箱はハイブリッドデザインで作成してください。\n'
            '新規作成時に「ハイブリッドデザイン」を選択してから実行してください。'
        )

    try:
        box_index = len(root_comp.occurrences) + 1
        box_name = 'RSC_Box_{:03d}'.format(box_index)

        transform = adsk.core.Matrix3D.create()
        box_occ = root_comp.occurrences.addNewComponent(transform)
        box_occ.component.name = box_name

        return box_occ, box_name

    except:
        raise ValueError(
            'A式箱はハイブリッドデザインで作成してください。\n'
            '新規作成時に「ハイブリッドデザイン」を選択してから実行してください。'
        )

# -------------------------
# 03-2. 底板作成
# -------------------------

def create_bottom_panel(box_occ, outer_width, outer_depth, thickness):
    box_comp = box_occ.component

    # mm -> cm
    width_cm = outer_width / 10.0
    depth_cm = outer_depth / 10.0
    thickness_cm = thickness / 10.0

    # 底板は前のコードと同じ考え方にします
    # X方向 = 横幅
    # Y方向 = 板厚
    # Z方向 = 奥行
    sketch = box_comp.sketches.add(box_comp.xYConstructionPlane)

    point1 = adsk.core.Point3D.create(0, 0, 0)
    point2 = adsk.core.Point3D.create(width_cm, thickness_cm, 0)

    sketch.sketchCurves.sketchLines.addTwoPointRectangle(point1, point2)

    profile = sketch.profiles.item(0)

    extrudes = box_comp.features.extrudeFeatures
    depth_input = adsk.core.ValueInput.createByReal(depth_cm)

    extrude_feature = extrudes.addSimple(
        profile,
        depth_input,
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation
    )

    bottom_body = extrude_feature.bodies.item(0)
    bottom_body.name = "Bottom_Panel"

# -------------------------
# 03-3. 背面パネル作成
# -------------------------

def create_back_panel(box_occ, outer_width, outer_height, thickness):
    box_comp = box_occ.component

    # mm -> cm
    width_cm = outer_width / 10.0
    height_cm = outer_height / 10.0
    thickness_cm = thickness / 10.0

    # 奥側の壁
    # X方向 = 横幅
    # Y方向 = 高さ
    # Z方向 = 板厚
    sketch = box_comp.sketches.add(box_comp.xYConstructionPlane)

    point1 = adsk.core.Point3D.create(0, thickness_cm, 0)
    point2 = adsk.core.Point3D.create(width_cm, height_cm - thickness_cm, 0)

    sketch.sketchCurves.sketchLines.addTwoPointRectangle(point1, point2)

    profile = sketch.profiles.item(0)

    extrudes = box_comp.features.extrudeFeatures
    thickness_input = adsk.core.ValueInput.createByReal(thickness_cm)

    extrude_feature = extrudes.addSimple(
        profile,
        thickness_input,
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation
    )

    back_body = extrude_feature.bodies.item(0)
    back_body.name = "Back_Panel"

# -------------------------
# 03-4. 前面パネル作成
# -------------------------

def create_front_panel(box_occ, outer_width, outer_depth, outer_height, thickness):
    box_comp = box_occ.component

    # mm -> cm
    width_cm = outer_width / 10.0
    depth_cm = outer_depth / 10.0
    height_cm = outer_height / 10.0
    thickness_cm = thickness / 10.0

    # 前面の壁
    # X方向 = 横幅
    # Y方向 = 高さ
    # Z方向 = 板厚
    sketch = box_comp.sketches.add(box_comp.xYConstructionPlane)

    point1 = adsk.core.Point3D.create(0, thickness_cm, 0)
    point2 = adsk.core.Point3D.create(width_cm, height_cm - thickness_cm, 0)

    sketch.sketchCurves.sketchLines.addTwoPointRectangle(point1, point2)

    profile = sketch.profiles.item(0)

    extrudes = box_comp.features.extrudeFeatures
    thickness_input = adsk.core.ValueInput.createByReal(thickness_cm)

    extrude_feature = extrudes.addSimple(
        profile,
        thickness_input,
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation
    )

    front_body = extrude_feature.bodies.item(0)
    front_body.name = "Front_Panel"

    # 前面を奥行方向へ移動する
    move_features = box_comp.features.moveFeatures

    body_collection = adsk.core.ObjectCollection.create()
    body_collection.add(front_body)

    move_transform = adsk.core.Matrix3D.create()
    move_transform.translation = adsk.core.Vector3D.create(
        0,
        0,
        depth_cm - thickness_cm
    )

    move_input = move_features.createInput(body_collection, move_transform)
    move_features.add(move_input)

# -------------------------
# 03-5. 左側面パネル作成
# -------------------------
def create_left_side_panel(box_occ, outer_depth, outer_height, thickness):
    box_comp = box_occ.component

    # mm -> cm
    depth_cm = outer_depth / 10.0
    height_cm = outer_height / 10.0
    thickness_cm = thickness / 10.0

    # 左側面の壁
    # まずXY平面に 奥行 × 高さ の板を作る
    # X方向 = 奥行
    # Y方向 = 高さ
    # Z方向 = 板厚
    sketch = box_comp.sketches.add(box_comp.xYConstructionPlane)

    point1 = adsk.core.Point3D.create(0, thickness_cm, 0)
    point2 = adsk.core.Point3D.create(depth_cm - thickness_cm * 2, height_cm - thickness_cm, 0)

    sketch.sketchCurves.sketchLines.addTwoPointRectangle(point1, point2)

    profile = sketch.profiles.item(0)

    extrudes = box_comp.features.extrudeFeatures
    thickness_input = adsk.core.ValueInput.createByReal(thickness_cm)

    extrude_feature = extrudes.addSimple(
        profile,
        thickness_input,
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation
    )

    left_body = extrude_feature.bodies.item(0)
    left_body.name = "Left_Side_Panel"

    # 左側面を90度回転して、YZ方向の壁にする
    move_features = box_comp.features.moveFeatures

    body_collection = adsk.core.ObjectCollection.create()
    body_collection.add(left_body)

    rotate_transform = adsk.core.Matrix3D.create()

    axis_point = adsk.core.Point3D.create(0, 0, 0)
    axis_vector = adsk.core.Vector3D.create(0, 1, 0)

    rotate_transform.setToRotation(
        3.1415926535 / 2,
        axis_vector,
        axis_point
    )

    rotate_input = move_features.createInput(body_collection, rotate_transform)
    move_features.add(rotate_input)

    # 左側面を箱の左端へ移動する
    move_collection = adsk.core.ObjectCollection.create()
    move_collection.add(left_body)

    move_transform = adsk.core.Matrix3D.create()
    move_transform.translation = adsk.core.Vector3D.create(
        0,
        0,
        depth_cm - thickness_cm
    )

    move_input = move_features.createInput(move_collection, move_transform)
    move_features.add(move_input)

# -------------------------
# 03-6. 右側面パネル作成
# -------------------------
def create_right_side_panel(box_occ, outer_width, outer_depth, outer_height, thickness):
    box_comp = box_occ.component

    # mm -> cm
    width_cm = outer_width / 10.0
    depth_cm = outer_depth / 10.0
    height_cm = outer_height / 10.0
    thickness_cm = thickness / 10.0

    # 右側面の壁
    # まずXY平面に 奥行 × 高さ の板を作る
    # X方向 = 奥行
    # Y方向 = 高さ
    # Z方向 = 板厚
    sketch = box_comp.sketches.add(box_comp.xYConstructionPlane)

    point1 = adsk.core.Point3D.create(0, thickness_cm, 0)
    point2 = adsk.core.Point3D.create(depth_cm - thickness_cm * 2, height_cm - thickness_cm, 0)

    sketch.sketchCurves.sketchLines.addTwoPointRectangle(point1, point2)

    profile = sketch.profiles.item(0)

    extrudes = box_comp.features.extrudeFeatures
    thickness_input = adsk.core.ValueInput.createByReal(thickness_cm)

    extrude_feature = extrudes.addSimple(
        profile,
        thickness_input,
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation
    )

    right_body = extrude_feature.bodies.item(0)
    right_body.name = "Right_Side_Panel"

    # 右側面を90度回転して、YZ方向の壁にする
    move_features = box_comp.features.moveFeatures

    body_collection = adsk.core.ObjectCollection.create()
    body_collection.add(right_body)

    rotate_transform = adsk.core.Matrix3D.create()

    axis_point = adsk.core.Point3D.create(0, 0, 0)
    axis_vector = adsk.core.Vector3D.create(0, 1, 0)

    rotate_transform.setToRotation(
        3.1415926535 / 2,
        axis_vector,
        axis_point
    )

    rotate_input = move_features.createInput(body_collection, rotate_transform)
    move_features.add(rotate_input)

    # 右側面を箱の右端へ移動する
    move_collection = adsk.core.ObjectCollection.create()
    move_collection.add(right_body)

    move_transform = adsk.core.Matrix3D.create()
    move_transform.translation = adsk.core.Vector3D.create(
        width_cm - thickness_cm,
        0,
        depth_cm - thickness_cm
    )

    move_input = move_features.createInput(move_collection, move_transform)
    move_features.add(move_input)

# -------------------------
# 03-7. 底板と胴回りの結合
# -------------------------
def combine_base_panels(box_occ):
    box_comp = box_occ.component

    bodies = box_comp.bRepBodies

    bottom_body = bodies.itemByName("Bottom_Panel")
    back_body = bodies.itemByName("Back_Panel")
    front_body = bodies.itemByName("Front_Panel")
    left_body = bodies.itemByName("Left_Side_Panel")
    right_body = bodies.itemByName("Right_Side_Panel")

    if not bottom_body:
        raise ValueError("Bottom_Panel が見つかりません。")
    if not back_body:
        raise ValueError("Back_Panel が見つかりません。")
    if not front_body:
        raise ValueError("Front_Panel が見つかりません。")
    if not left_body:
        raise ValueError("Left_Side_Panel が見つかりません。")
    if not right_body:
        raise ValueError("Right_Side_Panel が見つかりません。")

    tool_bodies = adsk.core.ObjectCollection.create()
    tool_bodies.add(back_body)
    tool_bodies.add(front_body)
    tool_bodies.add(left_body)
    tool_bodies.add(right_body)

    combine_features = box_comp.features.combineFeatures
    combine_input = combine_features.createInput(bottom_body, tool_bodies)
    combine_input.operation = adsk.fusion.FeatureOperations.JoinFeatureOperation
    combine_input.isKeepToolBodies = False

    combine_feature = combine_features.add(combine_input)

    base_body = combine_feature.bodies.item(0)
    base_body.name = "Base_Shell"

# -------------------------
# 03-8. 上側内フラップ作成
# -------------------------
def create_top_inner_flaps(box_occ, inner_depth, outer_width, outer_height, thickness):
    box_comp = box_occ.component

    # mm -> cm
    inner_depth_cm = inner_depth / 10.0
    outer_width_cm = outer_width / 10.0
    outer_height_cm = outer_height / 10.0
    thickness_cm = thickness / 10.0

    # 内フラップ寸法
    # サイズ: 内寸奥行 × 内寸奥行の半分
    inner_flap_length = inner_depth_cm / 2.0
    inner_flap_width = inner_depth_cm

    # 左側の上内フラップを作る
    # X方向 = フラップの出る長さ
    # Y方向 = 板厚
    # Z方向 = フラップの幅
    sketch = box_comp.sketches.add(box_comp.xYConstructionPlane)

    point1 = adsk.core.Point3D.create(0, 0, 0)
    point2 = adsk.core.Point3D.create(inner_flap_length, thickness_cm, 0)

    sketch.sketchCurves.sketchLines.addTwoPointRectangle(point1, point2)

    profile = sketch.profiles.item(0)

    extrudes = box_comp.features.extrudeFeatures
    width_input = adsk.core.ValueInput.createByReal(inner_flap_width)

    left_extrude = extrudes.addSimple(
        profile,
        width_input,
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation
    )

    left_flap_body = left_extrude.bodies.item(0)
    left_flap_body.name = "Top_Left_Inner_Flap"

    # 左側の上内フラップを箱の上へ移動する
    move_features = box_comp.features.moveFeatures

    left_collection = adsk.core.ObjectCollection.create()
    left_collection.add(left_flap_body)

    left_transform = adsk.core.Matrix3D.create()
    left_transform.translation = adsk.core.Vector3D.create(
        thickness_cm,
        outer_height_cm - thickness_cm * 2,
        thickness_cm
    )

    left_move_input = move_features.createInput(left_collection, left_transform)
    move_features.add(left_move_input)

    # 右側の上内フラップを作る
    right_extrude = extrudes.addSimple(
        profile,
        width_input,
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation
    )

    right_flap_body = right_extrude.bodies.item(0)
    right_flap_body.name = "Top_Right_Inner_Flap"

    # 右側の上内フラップを箱の上へ移動する
    right_collection = adsk.core.ObjectCollection.create()
    right_collection.add(right_flap_body)

    right_transform = adsk.core.Matrix3D.create()
    right_transform.translation = adsk.core.Vector3D.create(
        outer_width_cm - thickness_cm - inner_flap_length,
        outer_height_cm - thickness_cm * 2,
        thickness_cm
    )

    right_move_input = move_features.createInput(right_collection, right_transform)
    move_features.add(right_move_input)

# -------------------------
# 03-9. 下側内フラップ作成
# -------------------------
def create_bottom_inner_flaps(box_occ, inner_depth, outer_width, thickness):
    box_comp = box_occ.component

    # mm -> cm
    inner_depth_cm = inner_depth / 10.0
    outer_width_cm = outer_width / 10.0
    thickness_cm = thickness / 10.0

    # 内フラップ寸法
    # サイズ: 内寸奥行 × 内寸奥行の半分
    inner_flap_length = inner_depth_cm / 2.0
    inner_flap_width = inner_depth_cm

    # 左側の下内フラップを作る
    # X方向 = フラップの出る長さ
    # Y方向 = 板厚
    # Z方向 = フラップの幅
    sketch = box_comp.sketches.add(box_comp.xYConstructionPlane)

    point1 = adsk.core.Point3D.create(0, 0, 0)
    point2 = adsk.core.Point3D.create(inner_flap_length, thickness_cm, 0)

    sketch.sketchCurves.sketchLines.addTwoPointRectangle(point1, point2)

    profile = sketch.profiles.item(0)

    extrudes = box_comp.features.extrudeFeatures
    width_input = adsk.core.ValueInput.createByReal(inner_flap_width)

    left_extrude = extrudes.addSimple(
        profile,
        width_input,
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation
    )

    left_flap_body = left_extrude.bodies.item(0)
    left_flap_body.name = "Bottom_Left_Inner_Flap"

    # 左側の下内フラップを箱の下側へ移動する
    move_features = box_comp.features.moveFeatures

    left_collection = adsk.core.ObjectCollection.create()
    left_collection.add(left_flap_body)

    left_transform = adsk.core.Matrix3D.create()
    left_transform.translation = adsk.core.Vector3D.create(
        thickness_cm,
        thickness_cm,
        thickness_cm
    )

    left_move_input = move_features.createInput(left_collection, left_transform)
    move_features.add(left_move_input)

    # 右側の下内フラップを作る
    right_extrude = extrudes.addSimple(
        profile,
        width_input,
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation
    )

    right_flap_body = right_extrude.bodies.item(0)
    right_flap_body.name = "Bottom_Right_Inner_Flap"

    # 右側の下内フラップを箱の下側へ移動する
    right_collection = adsk.core.ObjectCollection.create()
    right_collection.add(right_flap_body)

    right_transform = adsk.core.Matrix3D.create()
    right_transform.translation = adsk.core.Vector3D.create(
        outer_width_cm - thickness_cm - inner_flap_length,
        thickness_cm,
        thickness_cm
    )

    right_move_input = move_features.createInput(right_collection, right_transform)
    move_features.add(right_move_input)

# -------------------------
# 03-10. 上側外フラップ作成
# -------------------------
def create_top_outer_flaps(box_occ, outer_width, outer_depth, outer_height, thickness):
    box_comp = box_occ.component

    # mm -> cm
    outer_width_cm = outer_width / 10.0
    outer_depth_cm = outer_depth / 10.0
    outer_height_cm = outer_height / 10.0
    thickness_cm = thickness / 10.0

    # 外フラップ共通寸法
    # サイズ: 外寸横幅 × 外寸奥行の半分
    outer_flap_width = outer_width_cm
    outer_flap_length = outer_depth_cm / 2.0

    # 奥側の上外フラップを作る
    # X方向 = 外寸横幅
    # Y方向 = 板厚
    # Z方向 = 外寸奥行の半分
    sketch = box_comp.sketches.add(box_comp.xYConstructionPlane)

    point1 = adsk.core.Point3D.create(0, 0, 0)
    point2 = adsk.core.Point3D.create(outer_flap_width, thickness_cm, 0)

    sketch.sketchCurves.sketchLines.addTwoPointRectangle(point1, point2)

    profile = sketch.profiles.item(0)

    extrudes = box_comp.features.extrudeFeatures
    length_input = adsk.core.ValueInput.createByReal(outer_flap_length)

    back_extrude = extrudes.addSimple(
        profile,
        length_input,
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation
    )

    back_flap_body = back_extrude.bodies.item(0)
    back_flap_body.name = "Top_Back_Outer_Flap"

    # 奥側の上外フラップを箱の上へ移動する
    move_features = box_comp.features.moveFeatures

    back_collection = adsk.core.ObjectCollection.create()
    back_collection.add(back_flap_body)

    back_transform = adsk.core.Matrix3D.create()
    back_transform.translation = adsk.core.Vector3D.create(
        0,
        outer_height_cm - thickness_cm,
        thickness_cm - thickness_cm
    )

    back_move_input = move_features.createInput(back_collection, back_transform)
    move_features.add(back_move_input)

    # 手前側の上外フラップを作る
    front_extrude = extrudes.addSimple(
        profile,
        length_input,
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation
    )

    front_flap_body = front_extrude.bodies.item(0)
    front_flap_body.name = "Top_Front_Outer_Flap"

    # 手前側の上外フラップを箱の上へ移動する
    front_collection = adsk.core.ObjectCollection.create()
    front_collection.add(front_flap_body)

    front_transform = adsk.core.Matrix3D.create()
    front_transform.translation = adsk.core.Vector3D.create(
        0,
        outer_height_cm - thickness_cm,
        outer_depth_cm - outer_flap_length
    )

    front_move_input = move_features.createInput(front_collection, front_transform)
    move_features.add(front_move_input)

# -------------------------
# 03-11. 色設定
# -------------------------
def apply_cardboard_appearance(box_occ):
    design = adsk.fusion.Design.cast(_app.activeProduct)
    box_comp = box_occ.component

    appearance = design.appearances.itemByName("RSC_Cardboard_Color")

    if appearance is None:
        source_appearance = None

        for lib_index in range(_app.materialLibraries.count):
            material_lib = _app.materialLibraries.item(lib_index)

            for app_index in range(material_lib.appearances.count):
                candidate_appearance = material_lib.appearances.item(app_index)

                if "段ボール" in candidate_appearance.name:
                    source_appearance = candidate_appearance
                    break

            if source_appearance:
                break

        if source_appearance is None:
            return

        appearance = design.appearances.addByCopy(
            source_appearance,
            "RSC_Cardboard_Color"
        )

    for body in box_comp.bRepBodies:
        body.appearance = appearance

# -------------------------
# 03-12. 箱情報保存
# -------------------------
def save_box_dimensions(box_occ, inner_width, inner_depth, inner_height, thickness, outer_width, outer_depth, outer_height):
    attributes = box_occ.component.attributes

    attributes.add('RSCBoxCreator', 'InnerWidth', str(inner_width))
    attributes.add('RSCBoxCreator', 'InnerDepth', str(inner_depth))
    attributes.add('RSCBoxCreator', 'InnerHeight', str(inner_height))
    attributes.add('RSCBoxCreator', 'Thickness', str(thickness))

    attributes.add('RSCBoxCreator', 'OuterWidth', str(outer_width))
    attributes.add('RSCBoxCreator', 'OuterDepth', str(outer_depth))
    attributes.add('RSCBoxCreator', 'OuterHeight', str(outer_height))

    attributes.add('RSCBoxMotion', 'State', 'closed')

# =========================
# 04.コマンド実行時の処理
# =========================

class CreateBoxCommandExecuteHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        try:
            check_hybrid_design()
            
            input_result = _ui.inputBox(
                '内寸 横幅, 奥行, 高さ, 板厚 mm を入力してください。\n\n'
                '例: 400,250,100,5',
                'A式箱 寸法入力',
                ''
            )

            # キャンセルされたら何もしない
            if input_result[1]:
                return

            size_text = input_result[0]

            length, width, height, thickness = parse_box_size(size_text)
            outer_width, outer_depth, outer_height = calc_outer_size(length, width, height, thickness)

            box_occ, box_name = create_box_component()
            create_bottom_panel(box_occ, outer_width, outer_depth, thickness)
            create_back_panel(box_occ, outer_width, outer_height, thickness)
            create_front_panel(box_occ, outer_width, outer_depth, outer_height, thickness)
            create_left_side_panel(box_occ, outer_depth, outer_height, thickness)
            create_right_side_panel(box_occ, outer_width, outer_depth, outer_height, thickness)
            combine_base_panels(box_occ)
            create_top_inner_flaps(box_occ, width, outer_width, outer_height, thickness)
            create_bottom_inner_flaps(box_occ, width, outer_width, thickness)
            create_top_outer_flaps(box_occ, outer_width, outer_depth, outer_height, thickness)
            apply_cardboard_appearance(box_occ)
            save_box_dimensions(
                box_occ,
                length,
                width,
                height,
                thickness,
                outer_width,
                outer_depth,
                outer_height
            )

            # 完了メッセージは出さない

        except ValueError as e:
            if _ui:
                _ui.messageBox(str(e))

        except:
            if _ui:
                _ui.messageBox(
                    'A式箱はハイブリッドデザインで作成してください。\n'
                    '新規作成時に「ハイブリッドデザイン」を選択してから実行してください。'
                )

# =========================
# 05.コマンド作成時の処理
# =========================

class CreateBoxCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        try:
            cmd = args.command

            # 入力欄はFusion標準ダイアログではなく、実行時に inputBox で出す
            cmd.isAutoExecute = True

            on_execute = CreateBoxCommandExecuteHandler()
            cmd.execute.add(on_execute)
            _handlers.append(on_execute)

        except:
            if _ui:
                _ui.messageBox('コマンド作成エラー:\n{}'.format(traceback.format_exc()))

# =========================
# 06.アドイン開始
# =========================

def run(context):
    global _app, _ui

    try:
        _app = adsk.core.Application.get()
        _ui = _app.userInterface

        cmd_defs = _ui.commandDefinitions

        existing_cmd = cmd_defs.itemById(COMMAND_ID)
        if existing_cmd:
            existing_cmd.deleteMe()

        cmd_def = cmd_defs.addButtonDefinition(
            COMMAND_ID,
            COMMAND_NAME,
            COMMAND_DESCRIPTION,
            "resources/create"
        )

        on_command_created = CreateBoxCommandCreatedHandler()
        cmd_def.commandCreated.add(on_command_created)
        _handlers.append(on_command_created)

        workspace = _ui.workspaces.itemById('FusionSolidEnvironment')
        toolbar_panel = workspace.toolbarPanels.itemById(PANEL_ID)

        existing_control = toolbar_panel.controls.itemById(COMMAND_ID)
        if existing_control:
            existing_control.deleteMe()

        control = toolbar_panel.controls.addCommand(cmd_def)
        control.isPromoted = True
        control.isPromotedByDefault = True

    except:
        if _ui:
            _ui.messageBox('アドイン開始エラー:\n{}'.format(traceback.format_exc()))


# =========================
# 07.アドイン停止
# =========================

def stop(context):
    try:
        if _ui:
            workspace = _ui.workspaces.itemById('FusionSolidEnvironment')
            toolbar_panel = workspace.toolbarPanels.itemById(PANEL_ID)

            control = toolbar_panel.controls.itemById(COMMAND_ID)
            if control:
                control.deleteMe()

            cmd_def = _ui.commandDefinitions.itemById(COMMAND_ID)
            if cmd_def:
                cmd_def.deleteMe()

    except:
        if _ui:
            _ui.messageBox('アドイン停止エラー:\n{}'.format(traceback.format_exc()))
                        
