import React, { useState, useEffect, useCallback } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Button,
  Box,
  CircularProgress,
} from '@mui/material';
import { styled } from '@mui/material/styles';
import { TransitionGroup, CSSTransition } from 'react-transition-group';
import { getAttendance } from '../api';
import dayjs from 'dayjs';

const GlassDialog = styled(Dialog)(({ theme }) => ({
  '& .MuiDialog-paper': {
    backgroundColor: 'rgba(255, 255, 255, 0.15)',
    backdropFilter: 'blur(10px)',
    border: '1px solid rgba(255, 255, 255, 0.18)',
    boxShadow: '0 8px 32px 0 rgba(31, 38, 135, 0.37)',
    borderRadius: '10px',
  },
}));

const GlassContent = styled(Box)(({ theme }) => ({
  padding: theme.spacing(3),
  borderRadius: '10px',
  backgroundColor: 'rgba(255, 255, 255, 0.1)',
  backdropFilter: 'blur(10px)',
  border: '1px solid rgba(255, 255, 255, 0.18)',
}));

const StyledTableCell = styled(TableCell)(({ theme, status }) => ({
  padding: '8px',
  textAlign: 'center',
  fontWeight: 'bold',
  ...(status === 'P' && {
    backgroundColor: '#4CAF50',
    color: 'white',
  }),
  ...(status === 'A' && {
    backgroundColor: '#F44336',
    color: 'white',
  }),
  ...(status === 'TA' && {
    backgroundColor: '#FF1744',
    color: 'black',
  }),
  ...(status === 'O' && {
    backgroundColor: '#FFEB3B',
    color: 'black',
  }),
  ...(status === 'C' && {
    backgroundColor: '#FF9800',
    color: 'black',
  }),
}));

const SlideTransition = styled('div')(({ theme, direction }) => ({
  position: 'relative',
  width: '100%',
  '&.slide-enter': {
    transform: direction === 'left' ? 'translateX(100%)' : 'translateX(-100%)',
    opacity: 0,
  },
  '&.slide-enter-active': {
    transform: 'translateX(0%)',
    opacity: 1,
    transition: 'all 300ms ease-in',
  },
  '&.slide-exit': {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    transform: 'translateX(0%)',
    opacity: 1,
  },
  '&.slide-exit-active': {
    transform: direction === 'left' ? 'translateX(-100%)' : 'translateX(100%)',
    opacity: 0,
    transition: 'all 300ms ease-in',
  },
}));

const ContentWrapper = styled(Box)({
  position: 'relative',
  overflow: 'hidden',
});

const GlassButton = styled(Button)(({ theme }) => ({
  backgroundColor: 'rgba(255, 255, 255, 0.2)',
  backdropFilter: 'blur(5px)',
  border: '1px solid rgba(255, 255, 255, 0.18)',
  color: theme.palette.common.white,
  '&:hover': {
    backgroundColor: 'rgba(255, 255, 255, 0.3)',
  },
}));

const AttendanceOverviewModal = ({ open, onClose, trainerId, studentMap }) => {
  const [attendanceData, setAttendanceData] = useState({});
  const [currentMonth, setCurrentMonth] = useState(dayjs());
  const [loading, setLoading] = useState(false);
  const [slideDirection, setSlideDirection] = useState('left');

  const fetchAttendanceData = useCallback(async () => {
    if (!trainerId) return;

    setLoading(true);
    try {
      const startDate = currentMonth.startOf('month').format('YYYY-MM-DD');
      const endDate = currentMonth.endOf('month').format('YYYY-MM-DD');
      
      const attendanceResponse = await getAttendance({
        trainer: trainerId,
        start_date: startDate,
        end_date: endDate
      });

      const formattedData = {};
      attendanceResponse.data.forEach(attendance => {
        const studentId = attendance.student;
        const date = dayjs(attendance.timestamp).format('YYYY-MM-DD');
        if (!formattedData[studentId]) {
          formattedData[studentId] = {
            name: studentMap[studentId]?.name || `Student ${studentId}`,
            classTime: studentMap[studentId]?.classTime || 'N/A',
            attendance: {}
          };
        }
        formattedData[studentId].attendance[date] = attendance.status;
      });

      setAttendanceData(formattedData);
    } catch (error) {
      console.error('Error fetching attendance data:', error);
    } finally {
      setLoading(false);
    }
  }, [trainerId, currentMonth, studentMap]);

  useEffect(() => {
    if (open) {
      fetchAttendanceData();
    }
  }, [open, fetchAttendanceData]);

  const handlePreviousMonth = () => {
    setSlideDirection('right');
    setCurrentMonth(prev => prev.subtract(1, 'month'));
  };

  const handleNextMonth = () => {
    setSlideDirection('left');
    setCurrentMonth(prev => prev.add(1, 'month'));
  };

  const getStatusAbbreviation = (status) => {
    switch (status) {
      case 'PRESENT': return 'P';
      case 'ABSENT': return 'A';
      case 'TRAINER_ABSENT': return 'TA';
      case 'OFF': return 'O';
      case 'COMP': return 'C';
      default: return '-';
    }
  };

  const renderAttendanceTable = () => {
    const daysInMonth = currentMonth.daysInMonth();
    const days = Array.from({ length: daysInMonth }, (_, i) => i + 1);

    return (
      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Student Name</TableCell>
              <TableCell>Class Time</TableCell>
              {days.map(day => (
                <TableCell key={day} align="center">{day}</TableCell>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {Object.entries(attendanceData).map(([studentId, data]) => (
              <TableRow key={studentId}>
                <TableCell>{data.name}</TableCell>
                <TableCell>{data.classTime}</TableCell>
                {days.map(day => {
                  const date = currentMonth.date(day).format('YYYY-MM-DD');
                  const status = getStatusAbbreviation(data.attendance[date]);
                  return (
                    <StyledTableCell key={day} status={status}>
                      {status}
                    </StyledTableCell>
                  );
                })}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    );
  };

  const renderContent = () => (
    <GlassContent>
      <DialogTitle sx={{ color: 'white' }}>
        Attendance Overview - {currentMonth.format('MMMM YYYY')}
      </DialogTitle>
      <DialogContent>
        {loading ? (
          <Box display="flex" justifyContent="center" alignItems="center" height="300px">
            <CircularProgress />
          </Box>
        ) : (
          renderAttendanceTable()
        )}
      </DialogContent>
    </GlassContent>
  );

  return (
    <GlassDialog open={open} onClose={onClose} maxWidth="xl" fullWidth>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', p: 2 }}>
        <GlassButton onClick={handlePreviousMonth}>Previous Month</GlassButton>
        <GlassButton onClick={handleNextMonth}>Next Month</GlassButton>
      </Box>
      <ContentWrapper>
        <TransitionGroup>
          <CSSTransition
            key={currentMonth.format('YYYY-MM')}
            classNames="slide"
            timeout={300}
          >
            <SlideTransition direction={slideDirection}>
              {renderContent()}
            </SlideTransition>
          </CSSTransition>
        </TransitionGroup>
      </ContentWrapper>
    </GlassDialog>
  );
};

export default AttendanceOverviewModal;