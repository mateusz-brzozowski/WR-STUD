#!/usr/bin/env python3
from ev3dev2.motor import LargeMotor, MediumMotor, OUTPUT_A, OUTPUT_B, OUTPUT_C
from ev3dev2.sensor import INPUT_1, INPUT_2, INPUT_3, INPUT_4
from ev3dev2.sensor.lego import TouchSensor, ColorSensor, InfraredSensor
from ev3dev2.sound import Sound

from typing import Tuple, List

from time import sleep
import sys

##################
#                #
#    SETTINGS    #
#                #
##################

FORWARD_SPEED_AT_TURNS = 2

MIN_FORWARD_SPEED = 5
MAX_FORWARD_SPEED = 10

FORWARD_SPEED_CORRECTION = (
    (MAX_FORWARD_SPEED - MIN_FORWARD_SPEED) / MAX_FORWARD_SPEED
)

CONSTANT_P = 4.0
CONSTANT_I = 0.01
CONSTANT_D = 4.0

HISDROP_DOWNRY_LOSS = 0.5

AMPLIFIER = 0.1

ROTATIONS_PER_FULL_ROTATION = 20
TIME_PER_FULL_ROTATION = 1
TIME_PER_MODE_CHANGE = 0.025  # 0.1
TIME_PER_PICK_UP = 1

#: No color.
# COLOR_NOCOLOR = 0
#: Black color.
# COLOR_BLACK = 1
#: Blue color.
# COLOR_BLUE = 2
#: Green color.
# COLOR_GREEN = 3
#: Yellow color.
# COLOR_YELLOW = 4
#: Red color.
# COLOR_RED = 5
#: White color.
# COLOR_WHITE = 6
#: Brown color.
# COLOR_BROWN = 7
DEFAULT_COLOR_PICK_UP = ColorSensor.COLOR_RED
DEFAULT_COLOR_DROP_DOWN = ColorSensor.COLOR_BLUE

PICK_UP = 0
DROP_DOWN = 1
COLORS: List[int] = []

###################
#                 #
#    CONSTANTS    #
#                 #
###################

SOUND_VOLUME = 100

LEFT = 0
RIGHT = 1

WINNING_SONG = (
    ('D4', 'e3'),      # intro anacrouse
    ('D4', 'e3'),
    ('D4', 'e3'),
    ('G4', 'h'),       # meas 1
    ('D5', 'h'),
    ('C5', 'e3'),      # meas 2
    ('B4', 'e3'),
    ('A4', 'e3'),
    ('G5', 'h'),
    ('D5', 'q'),
    ('C5', 'e3'),      # meas 3
    ('B4', 'e3'),
    ('A4', 'e3'),
    ('G5', 'h'),
    ('D5', 'q'),
    ('C5', 'e3'),      # meas 4
    ('B4', 'e3'),
    ('C5', 'e3'),
    ('A4', 'h.'),
)


#####################
#                   #
#    PERIPHERALS    #
#                   #
#####################

sound = Sound()
button = TouchSensor(INPUT_3)

left_motor = LargeMotor(OUTPUT_A)
right_motor = LargeMotor(OUTPUT_B)

motors = [left_motor, right_motor]

left_sensor = ColorSensor(INPUT_1)
right_sensor = ColorSensor(INPUT_2)

sensors = [left_sensor, right_sensor]

motor = MediumMotor(OUTPUT_C)
distance_sensor = InfraredSensor(INPUT_4)

distance_sensor.mode = distance_sensor.MODE_IR_PROX

# for _ in range(100):
#     print(distance_sensor.proximity)
#     sleep(0.1)


################
#              #
#    STATES    #
#              #
################

FOLLOW_LINE_UNTIL_PICK_UP = 0
FOLLOW_LINE_UNTIL_DETECTED_OBJECT = 1
FOLLOW_LINE_UNTIL_TWO_LINES_DETECTED = 2
FOLLOW_LINE_UNTIL_DROP_DOWN = 3
FOLLOW_LINE_UNTIL_TWO_DROP_DOWN_COLORS_DETECTED = 4
STATE_STOP = 5

######################
#                    #
#    MAIN PROGRAM    #
#                    #
######################


def speak(message: str) -> None:
    sound.speak(message)
    print(message)


def work() -> None:
    integral = 0.0
    last_error = 0

    state = FOLLOW_LINE_UNTIL_PICK_UP

    while True:
        if button.is_pressed:
            handle_button_pressed()
        else:
            try:
                state, integral, last_error = iteration(
                    state, integral, last_error
                )
            except Exception as e:
                print(e)


def iteration(state: int, integral: float, last_error: int) -> Tuple[int, float, int]:
    if state == FOLLOW_LINE_UNTIL_PICK_UP:
        colors = detect_colors()
        if colors[LEFT] == COLORS[PICK_UP]:
            turn_left()
            state = FOLLOW_LINE_UNTIL_DETECTED_OBJECT
        elif colors[RIGHT] == COLORS[PICK_UP]:
            turn_right()
            state = FOLLOW_LINE_UNTIL_DETECTED_OBJECT
        else:
            integral, last_error = follow_line(integral, last_error)
    elif state == FOLLOW_LINE_UNTIL_DETECTED_OBJECT:
        detected_distance = distance()
        if detected_distance < 2:
            pick_up()
            turn_around()
            state = FOLLOW_LINE_UNTIL_TWO_LINES_DETECTED
        else:
            integral, last_error = follow_line(integral, last_error)
    elif state == FOLLOW_LINE_UNTIL_TWO_LINES_DETECTED:
        colors = detect_colors()
        if colors[LEFT] == ColorSensor.COLOR_BLACK and colors[RIGHT] == ColorSensor.COLOR_BLACK:
            turn_right()
            state = FOLLOW_LINE_UNTIL_DROP_DOWN
        else:
            integral, last_error = follow_line(integral, last_error)
    elif state == FOLLOW_LINE_UNTIL_DROP_DOWN:
        colors = detect_colors()
        if colors[LEFT] == COLORS[DROP_DOWN]:
            turn_left()
            state = FOLLOW_LINE_UNTIL_TWO_DROP_DOWN_COLORS_DETECTED
        elif colors[RIGHT] == COLORS[DROP_DOWN]:
            turn_right()
            state = FOLLOW_LINE_UNTIL_TWO_DROP_DOWN_COLORS_DETECTED
        else:
            integral, last_error = follow_line(integral, last_error)
    elif state == FOLLOW_LINE_UNTIL_TWO_DROP_DOWN_COLORS_DETECTED:
        colors = detect_colors()
        if colors[LEFT] == COLORS[DROP_DOWN] and colors[RIGHT] == COLORS[DROP_DOWN]:
            drop_down()
            sound.play_song(WINNING_SONG)
            turn_around()
            state = STATE_STOP
        else:
            integral, last_error = follow_line(integral, last_error)
    else:
        handle_button_pressed()

    return state, integral, last_error


def handle_button_pressed() -> None:
    stop()
    speak('STOP')
    button.wait_for_released()
    button.wait_for_bump()
    speak('START')


def detect_colors() -> Tuple[int, int]:
    ensure_mode(ColorSensor.MODE_COL_COLOR)
    return (
        left_sensor.color,
        right_sensor.color
    )


def follow_line(integral: float, last_error: int) -> Tuple[float, int]:
    ensure_mode(ColorSensor.MODE_COL_REFLECT)
    error = left_sensor.reflected_light_intensity - \
        right_sensor.reflected_light_intensity

    integral = HISDROP_DOWNRY_LOSS * integral + error
    derivative = error - last_error
    last_error = error

    turn_speed = CONSTANT_P * error + CONSTANT_I * integral + CONSTANT_D * derivative

    forward_speed = max(
        MIN_FORWARD_SPEED,
        MAX_FORWARD_SPEED - FORWARD_SPEED_CORRECTION * abs(turn_speed)
    )

    left_motor.on(forward_speed + AMPLIFIER * turn_speed)
    right_motor.on(forward_speed - AMPLIFIER * turn_speed)

    return integral, last_error


def ensure_mode(color: str) -> None:
    left_sensor.mode = color
    right_sensor.mode = color
    sleep(TIME_PER_MODE_CHANGE)


def turn(full_roations: float, speed: int) -> None:
    rotations = ROTATIONS_PER_FULL_ROTATION * full_roations
    left_motor.on_for_rotations(
        FORWARD_SPEED_AT_TURNS + speed,
        rotations
    )
    right_motor.on_for_rotations(
        FORWARD_SPEED_AT_TURNS - speed,
        rotations
    )
    sleep(TIME_PER_FULL_ROTATION * full_roations)


def turn_around() -> None:
    turn(0.5, MIN_FORWARD_SPEED)


def turn_left() -> None:
    turn(0.25, MIN_FORWARD_SPEED)


def turn_right() -> None:
    turn(0.25, -MIN_FORWARD_SPEED)


def distance() -> int:
    return distance_sensor.proximity


def pick_up() -> None:
    stop()
    motor.on_for_rotations(-10, 0.25)
    sleep(TIME_PER_PICK_UP)


def drop_down() -> None:
    stop()
    motor.on_for_rotations(-10, 0.25)
    sleep(TIME_PER_PICK_UP)
    for m in motors:
        m.on_for_rotations(-MIN_FORWARD_SPEED, 1)
    sleep(TIME_PER_PICK_UP)


def stop() -> None:
    for m in motors:
        m.stop()


def main() -> None:
    sound.set_volume(SOUND_VOLUME)
    speak('READY')

    button.wait_for_bump()
    speak('START')

    try:
        work()
    except KeyboardInterrupt as e:
        stop()
        raise e


if __name__ == '__main__':
    if len(sys.argv) > 3:
        COLORS.append(int(sys.argv[1]))
        COLORS.append(int(sys.argv[2]))
    else:
        COLORS.append(DEFAULT_COLOR_PICK_UP)
        COLORS.append(DEFAULT_COLOR_DROP_DOWN)
    main()