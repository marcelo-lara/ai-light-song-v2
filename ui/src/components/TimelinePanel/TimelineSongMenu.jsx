import Menu from "@mui/material/Menu";
import MenuItem from "@mui/material/MenuItem";

export default function TimelineSongMenu({ anchorEl, open, onClose, songs, loadedSong, onSelectSong }) {
  return (
    <Menu anchorEl={anchorEl} open={open} onClose={onClose}>
      {songs.length ? songs.map((song) => <MenuItem key={song} selected={song === loadedSong} onClick={() => void onSelectSong(song)}>{song}</MenuItem>) : <MenuItem disabled>No songs found in data/songs</MenuItem>}
    </Menu>
  );
}