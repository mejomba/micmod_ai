$(document).ready(function () {
    String.prototype.insert = function(index, string) {
        if (index > 0) {
            return this.substring(0, index) + string + this.substring(index, this.length);
        }
        return string + this;
    };
    String.prototype.reverse_string=function() {return this.split("").reverse().join("");}
})