from enum import Enum
from typing import NamedTuple


class DeviceTypes(Enum):
    LOCK = 0
    OPENER = 2


class DeviceModes(Enum):
    pass


class LockModes(DeviceModes):
    DOOR_MODE = 2


class OpenerModes(DeviceModes):
    DOOR_MODE = 2
    CONTINUOUS_MODE = 3


class DeviceStates(Enum):
    pass


class LockStates(DeviceStates):
    UNCALIBRATED = 0
    LOCKED = 1
    UNLOCKING = 2
    UNLOCKED = 3
    LOCKING = 4
    UNLATCHED = 5
    UNLOCKED_LOCK_N_GO = 6
    UNLATCHING = 7
    MOTOR_BLOCKED = 254
    UNDEFINED = 255


class OpenerStates(DeviceStates):
    UNTRAINED = 0
    ONLINE = 1
    RTO_ACTIVE = 3
    OPEN = 5
    OPENING = 7
    BOOT_RUN = 253
    UNDEFINED = 255


class DoorSensorStates(DeviceStates):
    DEACTIVATED = 1
    DOOR_CLOSED = 2
    DOOR_OPENED = 3
    UNKNOWN = 4
    CALIBRATING = 5


ErrorStates = (
    LockStates.UNCALIBRATED,
    LockStates.MOTOR_BLOCKED,
    LockStates.UNDEFINED,
    OpenerStates.UNTRAINED,
    OpenerStates.UNDEFINED,
)


class DeviceActions(Enum):
    pass


class OpenerActions(DeviceActions):
    ACTIVATE_RTO = 1
    DEACTIVATE_RTO = 2
    ELECTRIC_STRIKE_ACTUATION = 3
    ACTIVATE_CONTINUOUS_MODE = 4
    DEACTIVATE_CONTINUOUS_MODE = 5


class LockActions(DeviceActions):
    UNLOCK = 1
    LOCK = 2
    UNLATCH = 3
    LOCK_N_GO = 4
    LOCK_N_GO_UNLATCH = 5


class FullDeviceState(NamedTuple):
    mode: DeviceModes
    state: DeviceStates
    doorsensorState: DoorSensorStates
    batteryCritical: bool = False
    keypadBatteryCritical: bool = False
    ringActionTimestamp: str = ""
    ringActionState: bool = False
    timestamp: str = ""
