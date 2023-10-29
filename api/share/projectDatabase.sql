CREATE TABLE IF NOT EXISTS Students (
    StudentId INTEGER PRIMARY KEY,
    FirstName TEXT,
    LastName TEXT,
    Email TEXT
);

CREATE TABLE IF NOT EXISTS Instructors (
    InstructorId INTEGER PRIMARY KEY,
    FirstName TEXT,
    LastName TEXT,
    Email TEXT
);
    
CREATE TABLE IF NOT EXISTS Classes (
    ClassId INTEGER PRIMARY KEY,
    InstructorId INT REFERENCES Instructors(InstructorId),
    Department TEXT,
    CourseCode TEXT,
    SectionNumber INTEGER,
    ClassName TEXT,
    CurrentEnrollment INTEGER,
    MaxEnrollment INTEGER,
    AutomaticEnrollmentFrozen INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS Enrollments (
    EnrollmentId INTEGER PRIMARY KEY,
    StudentId INT REFERENCES Students(StudentId),
    ClassId INT REFERENCES Classes(ClassId),
    EnrollmentDate TEXT,
    Dropped INT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS WaitingLists (
    WaitListId INTEGER PRIMARY KEY,
    StudentId INT REFERENCES Students(StudentId),
    ClassId INT REFERENCES Classes(ClassId),
    WaitingListPos INT,
    DateAdded TEXT
);

-- Insert six students with names starting with 'S'
INSERT INTO Students(FirstName,LastName,Email)
VALUES
    ('Sam', 'Doe', 'SamDoe123@gmail.com'),
    ('Samantha', 'Smith', 'SamathaSmith123@gmail.com'),
    ('Sandra', 'Johnson', 'SandraJohnson123@gmail.com'),
    ('Steve', 'Brown', 'SteveBrown123@gmail.com'),
    ('Sylvia', 'Wilson', 'SylviaWilson123@gmail.com'),
    ('Scott', 'Davis', 'ScottDavis123@gmail.com')

-- Insert three professors with names starting with 'I'
INSERT INTO Instructors (FirstName,LastName,Email)
VALUES
    ('Mike','Garcia','MikeGarcia@gmail.com'),
    ('Denise','Jones','DeniseJones@gmail.com'),
    ('Zack','Smith','ZackSmith@gmail.com')

-- Insert six courses
INSERT INTO Classes(Department,CourseCode,SectionNumber,ClassName,InstructorID,CurrentEnrollment,MaxEnrollment)
VALUES
    ('Computer Science','CPSC351',1,'Operating Systems',5,30,45),
    ('Computer Science','CPSC240',2,'Assembly',4,23,30),
    ('Computer Science','CPSC223',3,'Python',3,30,35)
