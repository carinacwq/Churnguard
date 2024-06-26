import { Box, Typography, useTheme } from "@mui/material";
import { tokens } from "../../theme";

// code for style of statbox used to format the components on dashboard page
const StatBox = ({ title, subtitle, icon, increase}) => {
    const theme = useTheme();
    const colors = tokens(theme.palette.mode);

    return (
        <Box width="100%" m="0 19px">
          <Box display="flex" justifyContent="space-between">
            <Box>
              {icon}
              <Typography
                variant="h5"
                fontWeight="600"
                sx={{ padding: "10px 10px 5px 5px" }}
              >
                {title}
              </Typography>
            </Box>
          </Box>
          <Box display="flex" justifyContent="space-between" mt="2px">
            <Typography variant="h5" sx={{ color: colors.greenAccent[500] , padding: "5px 10px 10px 10px"}} fontFamily={'\'SFMono-Regular\', Consolas, \'Liberation Mono\', Menlo, Courier, monospace'}>
              {subtitle}
            </Typography>
            <Typography
              variant="h5"
              fontStyle="italic"
              sx={{ color: colors.greenAccent[600] , padding: "10px 10px 5px 5px"}}
            >
              {increase}
            </Typography>
          </Box>
        </Box>
      );
    };
    
    export default StatBox;