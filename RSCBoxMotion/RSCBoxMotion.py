# RSCBoxMotion.py
# Fusion 360 Add-in
# RSCBoxCreatorで作成したA式箱を開閉するためのアドイン

import adsk.core
import adsk.fusion
import traceback


_app = None
_ui = None
_handlers = []


# =========================
# 01. アドイン設定
# =========================

ADDIN_NAME = 'RSCBoxMotion'
PANEL_ID = 'SolidModifyPanel'

TOGGLE_COMMAND_ID = 'RSCBoxMotion_ToggleBox'
TOGGLE_COMMAND_NAME = 'A式箱を開閉'
TOGGLE_COMMAND_DESCRIPTION = '選択したA式箱のフラップを開閉します。'

# =========================
# 02. 選択中の箱取得
# =========================

def get_selected_box_occurrence():
    selections = _ui.activeSelections

    if selections.count < 1:
        raise ValueError('開閉したい RSC_Box を選択してください。')

    selected_entity = selections.item(0).entity

    if isinstance(selected_entity, adsk.fusion.Occurrence):
        occ = selected_entity
    elif hasattr(selected_entity, 'assemblyContext') and selected_entity.assemblyContext:
        occ = selected_entity.assemblyContext
    else:
        raise ValueError('RSC_Box コンポーネント、またはその中のボディを選択してください。')

    if not occ.component.name.startswith('RSC_Box_'):
        raise ValueError('選択されたものは RSC_Box ではありません。')

    return occ

def get_box_state(box_occ):
    attributes = box_occ.component.attributes

    state_attr = attributes.itemByName('RSCBoxMotion', 'State')

    if state_attr is None:
        return 'closed'

    return state_attr.value

def set_box_state(box_occ, state):
    attributes = box_occ.component.attributes

    existing_attr = attributes.itemByName('RSCBoxMotion', 'State')

    if existing_attr:
        existing_attr.value = state
    else:
        attributes.add('RSCBoxMotion', 'State', state)

def get_flap_bodies(box_occ):
    box_comp = box_occ.component
    bodies = box_comp.bRepBodies

    flap_names = [
        'Top_Left_Inner_Flap',
        'Top_Right_Inner_Flap',
        'Bottom_Left_Inner_Flap',
        'Bottom_Right_Inner_Flap',
        'Top_Back_Outer_Flap',
        'Top_Front_Outer_Flap'
    ]

    flap_bodies = []

    for flap_name in flap_names:
        body = bodies.itemByName(flap_name)

        if body is None:
            raise ValueError('{} が見つかりません。'.format(flap_name))

        flap_bodies.append(body)

    return flap_bodies

def get_box_dimensions(box_occ):
    attributes = box_occ.component.attributes

    def read_value(name):
        attr = attributes.itemByName('RSCBoxCreator', name)

        if attr is None:
            raise ValueError('箱の寸法情報 {} が見つかりません。新しい RSCBoxCreator で作成した箱を使ってください。'.format(name))

        return float(attr.value)

    dimensions = {
        'inner_width': read_value('InnerWidth'),
        'inner_depth': read_value('InnerDepth'),
        'inner_height': read_value('InnerHeight'),
        'thickness': read_value('Thickness'),
        'outer_width': read_value('OuterWidth'),
        'outer_depth': read_value('OuterDepth'),
        'outer_height': read_value('OuterHeight')
    }

    return dimensions

def move_body_local(box_occ, body, local_x_cm, local_y_cm, local_z_cm):
    """
    選択した箱の向きを反映してボディを移動します。

    local_x_cm, local_y_cm, local_z_cm は、
    箱自身から見た X/Y/Z 方向の移動量です。
    箱全体を90度回転していても、その向きを反映した方向へ動かします。
    """

    box_transform = box_occ.transform

    origin = adsk.core.Point3D.create(0, 0, 0)
    target = adsk.core.Point3D.create(local_x_cm, local_y_cm, local_z_cm)

    origin.transformBy(box_transform)
    target.transformBy(box_transform)

    move_vector = adsk.core.Vector3D.create(
        target.x - origin.x,
        target.y - origin.y,
        target.z - origin.z
    )

    box_comp = box_occ.component
    move_features = box_comp.features.moveFeatures

    body_collection = adsk.core.ObjectCollection.create()
    body_collection.add(body)

    move_transform = adsk.core.Matrix3D.create()
    move_transform.translation = move_vector

    move_input = move_features.createInput(body_collection, move_transform)
    move_features.add(move_input)

# -------------------------
# 02-1. フラップを開く処理
# -------------------------
def open_box_flaps(box_occ):
    box_comp = box_occ.component
    bodies = box_comp.bRepBodies
    move_features = box_comp.features.moveFeatures

    dimensions = get_box_dimensions(box_occ)

    inner_depth_cm = dimensions['inner_depth'] / 10.0
    thickness_cm = dimensions['thickness'] / 10.0
    outer_depth_cm = dimensions['outer_depth'] / 10.0

    inner_flap_move_cm = inner_depth_cm / 2.0
    outer_flap_move_cm = outer_depth_cm / 2.0 - thickness_cm

    # 内フラップ4枚を開く
    # 移動方法:
    # 横方向 = フラップ長さ分
    # 上方向 = 板厚分
    inner_flap_settings = [
        ('Top_Left_Inner_Flap', -1),
        ('Top_Right_Inner_Flap', 1)
    ]

    for flap_name, x_direction in inner_flap_settings:
        flap_body = bodies.itemByName(flap_name)

        if flap_body is None:
            raise ValueError('{} が見つかりません。'.format(flap_name))

        move_body_local(
            box_occ,
            flap_body,
            inner_flap_move_cm * x_direction,
            thickness_cm,
            0
        )

    # 外フラップ2枚を開く
    # 移動方法:
    # 横方向 = フラップ長さ - 板厚
    # 上下方向 = 移動なし
    outer_flap_settings = [
        ('Top_Back_Outer_Flap', -1),
        ('Top_Front_Outer_Flap', 1)
    ]

    for flap_name, z_direction in outer_flap_settings:
        flap_body = bodies.itemByName(flap_name)

        if flap_body is None:
            raise ValueError('{} が見つかりません。'.format(flap_name))

        move_body_local(
            box_occ,
            flap_body,
            0,
            0,
            outer_flap_move_cm * z_direction
        )
    
# -------------------------
# 02-2. フラップを閉じる処理
# -------------------------
def close_box_flaps(box_occ):
    box_comp = box_occ.component
    bodies = box_comp.bRepBodies
    move_features = box_comp.features.moveFeatures

    dimensions = get_box_dimensions(box_occ)

    inner_depth_cm = dimensions['inner_depth'] / 10.0
    thickness_cm = dimensions['thickness'] / 10.0
    outer_depth_cm = dimensions['outer_depth'] / 10.0

    inner_flap_move_cm = inner_depth_cm / 2.0
    outer_flap_move_cm = outer_depth_cm / 2.0 - thickness_cm

    # 内フラップ2枚を閉じる
    # 開く処理と逆方向へ戻す
    inner_flap_settings = [
        ('Top_Left_Inner_Flap', 1),
        ('Top_Right_Inner_Flap', -1)
    ]

    for flap_name, x_direction in inner_flap_settings:
        flap_body = bodies.itemByName(flap_name)

        if flap_body is None:
            raise ValueError('{} が見つかりません。'.format(flap_name))

        move_body_local(
            box_occ,
            flap_body,
            inner_flap_move_cm * x_direction,
            -thickness_cm,
            0
        )

    # 外フラップ2枚を閉じる
    # 開く処理と逆方向へ戻す
    outer_flap_settings = [
        ('Top_Back_Outer_Flap', 1),
        ('Top_Front_Outer_Flap', -1)
    ]

    for flap_name, z_direction in outer_flap_settings:
        flap_body = bodies.itemByName(flap_name)

        if flap_body is None:
            raise ValueError('{} が見つかりません。'.format(flap_name))

        move_body_local(
            box_occ,
            flap_body,
            0,
            0,
            outer_flap_move_cm * z_direction
        )

# =========================
# 03. 開閉コマンド実行時の処理
# =========================

class ToggleBoxCommandExecuteHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        try:
            box_occ = get_selected_box_occurrence()
            state = get_box_state(box_occ)
            flap_bodies = get_flap_bodies(box_occ)

            if state == 'closed':
                open_box_flaps(box_occ)
                new_state = 'open'
            else:
                close_box_flaps(box_occ)
                new_state = 'closed'

            set_box_state(box_occ, new_state)

        except Exception as e:
            if _ui:
                _ui.messageBox(str(e))


# =========================
# 04. 開閉コマンド作成時の処理
# =========================

class ToggleBoxCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        try:
            cmd = args.command

            on_execute = ToggleBoxCommandExecuteHandler()
            cmd.execute.add(on_execute)
            _handlers.append(on_execute)

        except:
            if _ui:
                _ui.messageBox('開閉コマンド作成エラー:\n{}'.format(traceback.format_exc()))


# =========================
# 05. アドイン開始
# =========================

def run(context):
    global _app, _ui

    try:
        _app = adsk.core.Application.get()
        _ui = _app.userInterface

        cmd_defs = _ui.commandDefinitions

        existing_toggle_cmd = cmd_defs.itemById(TOGGLE_COMMAND_ID)
        if existing_toggle_cmd:
            existing_toggle_cmd.deleteMe()

        toggle_cmd_def = cmd_defs.addButtonDefinition(
            TOGGLE_COMMAND_ID,
            TOGGLE_COMMAND_NAME,
            TOGGLE_COMMAND_DESCRIPTION,
            "resources/toggle"
        )

        on_toggle_created = ToggleBoxCommandCreatedHandler()
        toggle_cmd_def.commandCreated.add(on_toggle_created)
        _handlers.append(on_toggle_created)

        workspace = _ui.workspaces.itemById('FusionSolidEnvironment')
        toolbar_panel = workspace.toolbarPanels.itemById(PANEL_ID)

        existing_toggle_control = toolbar_panel.controls.itemById(TOGGLE_COMMAND_ID)
        if existing_toggle_control:
            existing_toggle_control.deleteMe()

        toolbar_panel.controls.addCommand(toggle_cmd_def)

    except:
        if _ui:
            _ui.messageBox('アドイン開始エラー:\n{}'.format(traceback.format_exc()))


# =========================
# 06. アドイン停止
# =========================

def stop(context):
    try:
        if _ui:
            workspace = _ui.workspaces.itemById('FusionSolidEnvironment')
            toolbar_panel = workspace.toolbarPanels.itemById(PANEL_ID)

            toggle_control = toolbar_panel.controls.itemById(TOGGLE_COMMAND_ID)
            if toggle_control:
                toggle_control.deleteMe()

            toggle_cmd_def = _ui.commandDefinitions.itemById(TOGGLE_COMMAND_ID)
            if toggle_cmd_def:
                toggle_cmd_def.deleteMe()

    except:
        if _ui:
            _ui.messageBox('アドイン停止エラー:\n{}'.format(traceback.format_exc()))
