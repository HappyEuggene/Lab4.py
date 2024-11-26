import csv
import copy
from collections import defaultdict
from tabulate import tabulate
import re
import math

# Data Structures
class Auditorium:
    def __init__(self, auditorium_id, capacity):
        self.id = auditorium_id
        self.capacity = int(capacity)

class Group:
    def __init__(self, group_number, student_amount, subgroups):
        self.number = group_number
        self.size = int(student_amount)
        self.subgroups = subgroups.strip('"').split(';') if subgroups else []

class Lecturer:
    def __init__(self, lecturer_id, name, subjects_can_teach, types_can_teach, max_hours_per_week):
        self.id = lecturer_id
        self.name = name
        self.subjects_can_teach = [s.strip() for s in re.split(';|,', subjects_can_teach)] if subjects_can_teach else []
        self.types_can_teach = [t.strip() for t in re.split(';|,', types_can_teach)] if types_can_teach else []
        self.max_hours_per_week = int(max_hours_per_week)

class Subject:
    def __init__(self, subject_id, name, group_id, num_lectures, num_practicals, requires_subgroups):
        self.id = subject_id
        self.name = name
        self.group_id = group_id
        self.num_lectures = int(num_lectures)
        self.num_practicals = int(num_practicals)
        self.requires_subgroups = True if requires_subgroups.lower() == 'yes' else False

# Functions to read CSV files
def read_auditoriums(filename):
    auditoriums = []
    with open(filename, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile, delimiter=';')
        for row in reader:
            auditoriums.append(Auditorium(row['auditoriumID'], row['capacity']))
    return auditoriums

def read_groups(filename):
    groups = []
    with open(filename, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile, delimiter=';')
        for row in reader:
            groups.append(Group(row['groupNumber'], row['studentAmount'], row['subgroups']))
    return groups

def read_lecturers(filename):
    lecturers = []
    with open(filename, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile, delimiter=';')
        for row in reader:
            lecturers.append(Lecturer(
                row['lecturerID'],
                row['lecturerName'],
                row['subjectsCanTeach'],
                row['typesCanTeach'],
                row['maxHoursPerWeek']
            ))
    return lecturers

def read_subjects(filename):
    subjects = []
    with open(filename, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile, delimiter=';')
        for row in reader:
            subjects.append(Subject(
                row['id'],
                row['name'],
                row['groupID'],
                row['numLectures'],
                row['numPracticals'],
                row['requiresSubgroups']
            ))
    return subjects

# Loading data
auditoriums = read_auditoriums('auditoriums.csv')
groups = read_groups('groups.csv')
lecturers = read_lecturers('lecturers.csv')
subjects = read_subjects('subjects.csv')

# Define time slots: 5 days, 4 periods per day
DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
PERIODS = ['1', '2', '3', '4']  # Periods per day
TIME_SLOTS = [(day, period) for day in DAYS for period in PERIODS]

# Define Lesson as a unique identifier for CSP variables
class Lesson:
    def __init__(self, lesson_id, subject, lesson_type, group, subgroup=None):
        self.id = lesson_id  # Unique identifier
        self.subject = subject
        self.type = lesson_type  # 'Лекція' або 'Практика'
        self.group = group
        self.subgroup = subgroup  # Для практичних занять, якщо необхідно

# Function to generate all lessons based on subjects
def generate_lessons(subjects, groups):
    lessons = []
    lesson_id = 0
    for subject in subjects:
        group = next((g for g in groups if g.number == subject.group_id), None)
        if not group:
            continue
        # Генерація лекцій
        for _ in range(subject.num_lectures):
            lessons.append(Lesson(lesson_id, subject, 'Лекція', group))
            lesson_id += 1
        # Генерація практичних занять
        if subject.requires_subgroups and group.subgroups:
            num_practicals_per_subgroup = math.ceil(subject.num_practicals / len(group.subgroups))
            for subgroup in group.subgroups:
                for _ in range(num_practicals_per_subgroup):
                    lessons.append(Lesson(lesson_id, subject, 'Практика', group, subgroup))
                    lesson_id += 1
        else:
            for _ in range(subject.num_practicals):
                lessons.append(Lesson(lesson_id, subject, 'Практика', group))
                lesson_id += 1
    return lessons

# Generate all lessons
lessons = generate_lessons(subjects, groups)

# Define CSP Variables and Domains
class CSP:
    def __init__(self, variables, domains, lecturers, auditoriums):
        self.variables = variables  # List of Lesson objects
        self.domains = domains      # Dict: lesson_id -> list of possible assignments (day, period, aud, lect)
        self.lecturers = lecturers
        self.auditoriums = auditoriums

    def is_consistent(self, assignment, var, value):
        day, period, aud, lect = value
        # Жорсткі обмеження
        for other_var_id, other_value in assignment.items():
            other_day, other_period, other_aud, other_lect = other_value
            # Перевірка на той же час
            if day == other_day and period == other_period:
                # 1. Одна аудиторія одночасно
                if aud == other_aud:
                    return False
                # 2. Один викладач одночасно
                if lect == other_lect:
                    return False
                # 3. Одна група одночасно
                if self.variables[var].group.number == self.variables[other_var_id].group.number:
                    # Перевірка підгруп
                    if self.variables[var].subgroup and self.variables[other_var_id].subgroup:
                        if self.variables[var].subgroup == self.variables[other_var_id].subgroup:
                            return False
                    else:
                        return False

        # 4. Аудиторія має достатню місткість
        group_size = self.variables[var].group.size
        if self.variables[var].subgroup and self.variables[var].group.subgroups:
            group_size = math.ceil(group_size / len(self.variables[var].group.subgroups))
        auditorium = next((a for a in self.auditoriums if a.id == aud), None)
        if auditorium and auditorium.capacity < group_size:
            return False

        # 5. Викладач не перевищує максимальну кількість годин
        hours_assigned = sum(1 for v, val in assignment.items() if val[3] == lect)
        lecturer = next((l for l in self.lecturers if l.id == lect), None)
        if lecturer and hours_assigned >= lecturer.max_hours_per_week:
            return False

        # 6. Специфічні обмеження (наприклад, максимум занять викладача в день)
        # Можна додати тут перевірку на кількість занять викладача в конкретний день
        max_lecturer_daily_hours = 3  # Приклад: максимум 3 години на день
        daily_hours = sum(1 for v, val in assignment.items()
                          if val[3] == lect and val[0] == day)
        if daily_hours >= max_lecturer_daily_hours:
            return False

        return True

    def select_unassigned_variable(self, assignment):
        # Використовуємо MRV (Minimum Remaining Values) евристику
        unassigned_vars = [v for v in self.variables if v.id not in assignment]
        # MRV
        min_domain_size = min(len(self.domains[v.id]) for v in unassigned_vars)
        mrv_vars = [v for v in unassigned_vars if len(self.domains[v.id]) == min_domain_size]
        if len(mrv_vars) == 1:
            return mrv_vars[0]
        # Ступенева евристика (degree)
        max_degree = -1
        selected_var = None
        for var in mrv_vars:
            degree = 0
            for other_var in self.variables:
                if other_var.id != var.id and self.is_neighbor(var, other_var):
                    degree += 1
            if degree > max_degree:
                max_degree = degree
                selected_var = var
        return selected_var

    def is_neighbor(self, var1, var2):
        # Змінні є сусідніми, якщо вони мають спільні обмеження
        # Наприклад, належать до однієї групи або мають одного викладача
        if var1.group.number == var2.group.number:
            return True
        # Якщо є викладачі, які можуть вести обидва предмети
        common_lecturers = set(var1.subject.id for var1 in self.variables if var1.subject.id in var2.subject.id)
        if common_lecturers:
            return True
        return False

    def order_domain_values(self, var, assignment):
        # Евристика з найменш обмежувальним значенням (Least Constraining Value)
        def count_conflicts(value):
            day, period, aud, lect = value
            conflicts = 0
            for other_var in self.variables:
                if other_var.id in assignment:
                    continue
                for other_value in self.domains[other_var.id]:
                    other_day, other_period, other_aud, other_lect = other_value
                    if day == other_day and period == other_period:
                        if aud == other_aud or lect == other_lect:
                            conflicts += 1
                        if self.variables[var.id].group.number == other_var.group.number:
                            if self.variables[var.id].subgroup and other_var.subgroup:
                                if self.variables[var.id].subgroup == other_var.subgroup:
                                    conflicts += 1
                            else:
                                conflicts += 1
            return conflicts

        return sorted(self.domains[var.id], key=lambda value: count_conflicts(value))

    def backtrack(self, assignment):
        # Якщо всі змінні присвоєні, повертаємо присвоєння
        if len(assignment) == len(self.variables):
            return assignment

        # Вибір наступної змінної
        var = self.select_unassigned_variable(assignment)

        # Впорядкування значень за LCV
        ordered_values = self.order_domain_values(var, assignment)

        for value in ordered_values:
            if self.is_consistent(assignment, var.id, value):
                assignment[var.id] = value
                result = self.backtrack(assignment)
                if result:
                    return result
                del assignment[var.id]
        return None

    def solve(self):
        return self.backtrack({})

# Function to create domains for each lesson
def create_domains(lessons, lecturers, auditoriums):
    domains = {}
    for lesson in lessons:
        possible_values = []
        # Фільтруємо можливих викладачів
        possible_lecturers = [lect for lect in lecturers if
                              lesson.subject.id in lect.subjects_can_teach and
                              lesson.type in lect.types_can_teach]
        if not possible_lecturers:
            continue  # Не має можливих викладачів, рішення неможливе

        # Фільтруємо можливі аудиторії
        group_size = lesson.group.size
        if lesson.subgroup and lesson.group.subgroups:
            group_size = math.ceil(group_size / len(lesson.group.subgroups))
        suitable_auditoriums = [aud for aud in auditoriums if aud.capacity >= group_size]
        if not suitable_auditoriums:
            continue  # Не має аудиторій з достатньою місткістю

        for day, period in TIME_SLOTS:
            for aud in suitable_auditoriums:
                for lect in possible_lecturers:
                    possible_values.append((day, period, aud.id, lect.id))
        domains[lesson.id] = possible_values
    return domains

# Function to calculate fitness based on soft constraints
def calculate_fitness(schedule, groups):
    fitness = 0
    # Мінімізація кількості вікон (перерв) у розкладі для кожної групи
    for group in groups:
        daily_schedule = {day: [] for day in DAYS}
        for key, entries in schedule.items():
            day, period = key
            for entry in entries:
                if entry['Group'] == group.number or (group.subgroups and any(entry['Group'] == f"{group.number} (Підгрупа {sg})" for sg in group.subgroups)):
                    daily_schedule[day].append(int(period))
        # Рахуємо кількість вікон
        for day, periods in daily_schedule.items():
            if not periods:
                continue
            periods = sorted(periods)
            windows = 0
            for i in range(1, len(periods)):
                if periods[i] - periods[i-1] > 1:
                    windows += 1
            fitness += windows
    return fitness

# Generate domains
domains = create_domains(lessons, lecturers, auditoriums)

# Initialize CSP
csp = CSP(variables=lessons, domains=domains, lecturers=lecturers, auditoriums=auditoriums)

# Solve CSP
solution = csp.solve()

if not solution:
    print("Не вдалося знайти розклад, який задовольняє всі жорсткі обмеження.")
else:
    # Організуємо розклад для друку
    schedule = defaultdict(list)

    for lesson_id, (day, period, aud, lect_id) in solution.items():
        lesson = next((s for s in lessons if s.id == lesson_id), None)
        if not lesson:
            continue
        lecturer = next((l for l in lecturers if l.id == lect_id), None)
        auditorium = next((a for a in auditoriums if a.id == aud), None)
        entry = {
            'Timeslot': f"{day}, період {period}",
            'Group': f"{lesson.group.number}" + (f" (Підгрупа {lesson.subgroup})" if lesson.subgroup else ""),
            'Subject': lesson.subject.name,
            'Type': lesson.type,
            'Lecturer': lecturer.name if lecturer else "N/A",
            'Auditorium': auditorium.id if auditorium else "N/A",
            'Students': math.ceil(lesson.group.size / len(lesson.group.subgroups)) if lesson.subgroup else lesson.group.size,
            'Capacity': auditorium.capacity if auditorium else "N/A"
        }
        schedule[(day, period)].append(entry)

    # Функція для друку розкладу
    def print_schedule(schedule):
        headers = ['Timeslot', 'Group', 'Subject', 'Type', 'Lecturer', 'Auditorium', 'Students', 'Capacity']
        schedule_table = []
        for time_slot in sorted(schedule.keys(), key=lambda x: (DAYS.index(x[0]), int(x[1]))):
            for entry in schedule[time_slot]:
                row = [entry[h] for h in headers]
                schedule_table.append(row)
        print("\nРозклад на тиждень:\n")
        if schedule_table:
            print(tabulate(schedule_table, headers=headers, tablefmt="grid", stralign="center"))
        else:
            print("Немає занять.")

    # Друк розкладу та фітнесу
    print_schedule(schedule)
    fitness = calculate_fitness(schedule, groups)
    print(f"\nФітнес розкладу: {fitness} вікон")
