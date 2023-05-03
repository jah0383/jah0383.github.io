const CisInfo = {
	Name: "James Howe",
	Age: 22
};
const TransInfo = {
	Name: "Piper Howe",
	Age: 22
};

let myInfo = TransInfo;


Array.from(document.getElementsByClassName("Name")).forEach(elem => (elem.textContent = myInfo["Name"]));
//for (const [key, value] of Object.entries(myInfo)) {
//  console.log(key, value);
//}